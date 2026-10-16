#include "fat_tree_worker.h"
#include "providers/image/fat_tree_file.h"
#include "providers/image/local_file.h"
#include "platform/windows/worker_files.h"
#include <cstring>
#include <set>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace w = worker_files;
struct Channel {
    volatile LONG state;
    DWORD length;
    char digest[64];
};
static_assert(sizeof(Channel) == 72, "selected anonymous tree page header ABI");
constexpr std::size_t channel_bytes = sizeof(Channel) + fat_tree_frame_bytes;
struct View {
    void *value = nullptr;
    explicit View(HANDLE h) {
        value = MapViewOfFile(h, FILE_MAP_WRITE, 0, 0, channel_bytes);
        if (!value)
            w::fail("fat_tree_mapping");
    }
    ~View() {
        if (value)
            UnmapViewOfFile(value);
    }
    View(const View &) = delete;
    View &operator=(const View &) = delete;
};
const V &get(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("fat_tree_worker_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = get(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("fat_tree_worker_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw std::invalid_argument("fat_tree_worker_integer");
    return std::stoull(s);
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        throw std::invalid_argument("fat_tree_worker_shape");
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            throw std::invalid_argument("fat_tree_worker_shape");
}
bool equal(const V &a, const V &b) {
    return json::dump(a, fat_tree_json_limits()) == json::dump(b, fat_tree_json_limits());
}
json::Limits reply_limits() {
    json::Limits l;
    l.bytes = 32768;
    l.values = 512;
    l.depth = 12;
    return l;
}
V publication(const char *status, std::uint64_t count, const V &digest, const V &diagnostic = V{}) {
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-publication/1"))
        .put("status", V::string(status))
        .put("page_count", number(count))
        .put("sha256", digest)
        .put("diagnostic", diagnostic)
        .put("claims", fat_tree_claims());
}
void validate_publication(const V &v) {
    exact(v, {"schema", "status", "page_count", "sha256", "diagnostic", "claims"});
    if (text(v, "schema") != "org.disked.fat-tree-publication/1" ||
        !equal(get(v, "claims"), fat_tree_claims()))
        throw std::invalid_argument("fat_tree_worker_claims");
    const auto status = text(v, "status");
    if (status != "completed" && status != "cancelled" && status != "unavailable")
        throw std::invalid_argument("fat_tree_worker_status");
    const auto count = integer(v, "page_count");
    const auto &digest = get(v, "sha256");
    if (count) {
        const auto s = text(v, "sha256");
        if (s.size() != 71 || s.substr(0, 7) != "sha256:" ||
            s.find_first_not_of("0123456789abcdef", 7) != s.npos)
            throw std::invalid_argument("fat_tree_worker_digest");
    } else if (digest.kind != V::Kind::null)
        throw std::invalid_argument("fat_tree_worker_digest");
    if (status == "completed" && (!count || get(v, "diagnostic").kind != V::Kind::null))
        throw std::invalid_argument("fat_tree_worker_status");
    if (status == "unavailable") {
        const auto &diagnostic = get(v, "diagnostic");
        exact(diagnostic, {"code", "platform_code"});
        const auto code = text(diagnostic, "code");
        if (code.empty() || code.size() > 128 || code.find('\0') != code.npos ||
            !json::valid_utf8(code) || integer(diagnostic, "platform_code") > 0xffffffffULL)
            throw std::invalid_argument("fat_tree_worker_diagnostic");
    } else if (get(v, "diagnostic").kind != V::Kind::null)
        throw std::invalid_argument("fat_tree_worker_diagnostic");
}
ObservationWorkerProfile profile() {
    ObservationWorkerProfile p;
    p.prefix = "fat_tree";
    p.scope = "ordinary-local-file-fat-tree";
    p.input_schema = "org.disked.fat-tree-worker-input/1";
    p.reply_schema = "org.disked.fat-tree-worker-reply/1";
    p.observation_schema = "org.disked.fat-tree-worker-observation/1";
    p.role = L"__disked_fat_tree_reader_worker";
    p.attempt_prefix = "fat-tree-attempt:";
    p.records_field = "sha256";
    p.input_mapping_bytes = 32768;
    p.input_limits.bytes = 32764;
    p.input_limits.values = 8192;
    p.input_limits.depth = 16;
    p.input_limits.string_bytes = 4096;
    p.provider_limits = p.input_limits;
    p.reply_limits = reply_limits();
    p.payload_bytes = channel_bytes;
    p.validate_request = [](const V &h) {
        const auto input = fat_tree_input_from(h);
        if (integer(h, "capture_epoch") != input.capture_epoch)
            throw std::invalid_argument("fat_tree_worker_epoch");
    };
    p.validate_result = [](const V &v, const V &) { validate_publication(v); };
    return p;
}
V owner(const V &h) {
    auto out = V::object();
    for (const auto key : {"host_id", "code_sha256", "capture_epoch", "observer_epoch",
                           "worker_epoch", "attempt_id"})
        out.put(key, get(h, key));
    return out.put("request_digest", V::string(w::hash(json::dump(h, profile().input_limits))));
}
V request(const FatTreeInput &input) {
    auto v = fat_tree_input_value(input);
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *p = input.fixture.find(key))
            v.put(key, *p);
    return V::object()
        .put("capture_epoch", number(input.capture_epoch))
        .put("policy", V::object())
        .put("provider_input", std::move(v));
}
bool acknowledge_wait(Channel *channel, const std::function<bool()> &stop) {
    for (;;) {
        if (stop())
            return false;
        if (InterlockedCompareExchange(&channel->state, 0, 0) == 0)
            return true;
        Sleep(1);
    }
}
} // namespace
struct FatTreeWorker::Impl {
    FatTreeInput input;
    w::Handle mapping;
    std::unique_ptr<View> view;
    std::unique_ptr<ObservationWorker> worker;
    std::unique_ptr<FatTreeReplay> replay;
    std::uint64_t received = 0;
    std::string last_digest, diagnostic;
    bool failed = false;
    explicit Impl(const FatTreeInput &v) : input(v), replay(new FatTreeReplay(v)) {
    }
};
FatTreeWorker::FatTreeWorker(std::unique_ptr<Impl> p) : impl_(std::move(p)) {
}
FatTreeWorker::~FatTreeWorker() = default;
std::unique_ptr<FatTreeWorker> FatTreeWorker::prepare(const FatTreeInput &input) {
    validate_fat_tree_input(input);
    std::unique_ptr<Impl> p(new Impl(input));
    w::Security security;
    auto attributes = security.attributes;
    p->mapping = w::Handle(CreateFileMappingW(INVALID_HANDLE_VALUE, &attributes, PAGE_READWRITE, 0,
                                              static_cast<DWORD>(channel_bytes), nullptr));
    if (!p->mapping.valid())
        w::fail("fat_tree_mapping_create");
    p->view.reset(new View(p->mapping.value));
    p->worker = ObservationWorker::prepare(request(input), profile(), p->mapping.value);
    return std::unique_ptr<FatTreeWorker>(new FatTreeWorker(std::move(p)));
}
void FatTreeWorker::launch() {
    impl_->worker->launch();
}
void FatTreeWorker::release() {
    impl_->worker->release();
}
void FatTreeWorker::cancel() {
    impl_->worker->cancel();
}
bool FatTreeWorker::never_launched() const {
    return impl_->worker->never_launched();
}
bool FatTreeWorker::wait_entered(DWORD n) {
    return impl_->worker->wait_entered(n);
}
std::shared_ptr<const FatTreePage> FatTreeWorker::next_page() {
    auto &p = *impl_;
    if (p.failed)
        return {};
    auto *channel = static_cast<Channel *>(p.view->value);
    if (InterlockedCompareExchange(&channel->state, 2, 1) != 1)
        return {};
    try {
        MemoryBarrier();
        const auto length = channel->length;
        if (!length || length > fat_tree_frame_bytes)
            throw std::invalid_argument("fat_tree_page_publication");
        const std::string bytes(reinterpret_cast<const char *>(channel + 1), length),
            digest(channel->digest, 64);
        MemoryBarrier();
        if (channel->state != 2 || channel->length != length || w::hash(bytes) != digest)
            throw std::invalid_argument("fat_tree_page_digest");
        auto envelope = json::parse(bytes, fat_tree_json_limits());
        exact(envelope, {"schema", "owner", "frame"});
        if (text(envelope, "schema") != "org.disked.fat-tree-envelope/1" ||
            !equal(get(envelope, "owner"), owner(p.worker->binding())))
            throw std::invalid_argument("fat_tree_page_owner");
        const auto observed = p.worker->observe();
        const auto &process = get(observed, "worker"), &frame = get(envelope, "frame"),
                   &context = get(frame, "context");
        if (integer(process, "pid") != integer(context, "process_id") ||
            integer(process, "created") != integer(context, "process_created"))
            throw std::invalid_argument("fat_tree_page_process");
        auto reconstructed = p.replay->accept(frame);
        const auto sequence = integer(reconstructed, "sequence");
        if (sequence != p.received + 1)
            throw std::invalid_argument("fat_tree_page_sequence");
        auto owned_context = get(envelope, "owner");
        owned_context.put("pid", get(process, "pid"))
            .put("created", get(process, "created"))
            .put("frame_sha256", V::string("sha256:" + digest))
            .put("cancellation_requested", get(observed, "cancellation_requested"))
            .put("image_profile", V::string("ordinary-file-fat-tree"));
        auto owned_frame = frame;
        std::shared_ptr<const FatTreePage> retained(
            new FatTreePage(std::move(owned_frame), std::move(owned_context)));
        p.received = sequence;
        p.last_digest = text(reconstructed, "page_digest");
        MemoryBarrier();
        InterlockedExchange(&channel->state, 0);
        return retained;
    } catch (const std::exception &e) {
        p.failed = true;
        p.diagnostic = e.what();
        p.worker->cancel();
        return {};
    }
}
V FatTreeWorker::observe(DWORD n) {
    auto &p = *impl_;
    auto out = p.worker->observe(n);
    out.put("pages_received", number(p.received))
        .put("last_page_digest", p.last_digest.empty() ? V{} : V::string(p.last_digest));
    if (p.failed) {
        out.put("status", V::string("unknown"))
            .put("diagnostic", V::string(p.diagnostic))
            .put("result", V{});
        return out;
    }
    if (text(out, "status") == "completed") {
        const auto &result = get(out, "result");
        if (integer(result, "page_count") != p.received ||
            !equal(get(result, "sha256"), p.last_digest.empty() ? V{} : V::string(p.last_digest)))
            out.put("status", V::string("unknown"))
                .put("diagnostic", V::string("fat_tree_final_pages"))
                .put("result", V{});
    }
    return out;
}
V FatTreeWorker::retire(DWORD n) {
    impl_->worker->retire(n);
    return observe();
}
int fat_tree_worker_role(int argc, wchar_t **argv) {
    return observation_worker_role(
        argc, argv, profile(),
        PayloadObservationFactory([](const V &h, const std::function<void()> &notify,
                                     HANDLE handle) -> ObservationCollector {
            const auto input = fat_tree_input_from(h);
            auto view = std::make_shared<View>(handle);
            const auto launch_owner = owner(h);
            notify();
            return [input, view, launch_owner](const std::function<bool()> &stop) {
                auto *channel = static_cast<Channel *>(view->value);
                std::uint64_t published = 0;
                V last;
                try {
#ifdef DISKED_FAT_TREE_WORKER_TESTING
                    const auto *f = input.fixture.find("worker_fault");
                    const auto fault = f ? f->text : "";
                    if (fault == "hang")
                        for (;;)
                            Sleep(10);
                    if (fault == "late")
                        Sleep(200);
#endif
                    FatTreeFile source(input);
                    while (!source.finished()) {
                        if (stop())
                            return publication("cancelled", published, last);
                        auto frame = source.next(stop);
                        const auto candidate = get(get(frame, "page"), "page_digest");
                        auto envelope =
                            V::object()
                                .put("schema", V::string("org.disked.fat-tree-envelope/1"))
                                .put("owner", launch_owner)
                                .put("frame", std::move(frame));
#ifdef DISKED_FAT_TREE_WORKER_TESTING
                        if (published == 0) {
                            if (fault == "frame_changed")
                                envelope.fields.at("frame").fields.at("page").put(
                                    "status", V::string("invented"));
                            if (fault == "region_changed")
                                envelope.fields.at("frame").fields.at("regions").items.at(0).put(
                                    "bytes", V::string("00"));
                            if (fault == "checks_changed")
                                envelope.fields.at("frame").fields.at("checks").items.at(0).put(
                                    "read_consistent", V::boolean_value(false));
                            if (fault == "process_changed")
                                envelope.fields.at("frame").fields.at("context").put(
                                    "process_id", V::string("1"));
                            if (fault == "page_digest")
                                envelope.fields.at("frame").fields.at("page").put(
                                    "page_digest", V::string("sha256:" + std::string(64, '0')));
                            if (fault == "page_context")
                                envelope.fields.at("owner").put("worker_epoch", V::string("stale"));
                        }
#endif
                        const auto bytes = json::dump(envelope, fat_tree_json_limits()),
                                   digest = w::hash(bytes);
                        if (!acknowledge_wait(channel, stop))
                            return publication("cancelled", published, last);
                        channel->length = static_cast<DWORD>(bytes.size());
                        std::memcpy(channel + 1, bytes.data(), bytes.size());
                        std::memcpy(channel->digest, digest.data(), 64);
                        MemoryBarrier();
                        InterlockedExchange(&channel->state, 1);
                        ++published;
                        last = candidate;
#ifdef DISKED_FAT_TREE_WORKER_TESTING
                        if (fault == "hold")
                            Sleep(200);
#endif
                        if (!acknowledge_wait(channel, stop))
                            return publication("cancelled", published, last);
                    }
                    return publication(stop() ? "cancelled" : "completed", published, last);
                } catch (const local_file::Error &e) {
                    return publication("unavailable", published, last,
                                       V::object()
                                           .put("code", V::string(e.what()))
                                           .put("platform_code", number(e.platform_code)));
                } catch (const std::exception &e) {
                    return publication("unavailable", published, last,
                                       V::object()
                                           .put("code", V::string(e.what()))
                                           .put("platform_code", number(0)));
                }
            };
        }));
}
} // namespace nt_inventory
} // namespace disked
