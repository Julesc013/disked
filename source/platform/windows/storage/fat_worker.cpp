#include "fat_worker.h"
#include "platform/windows/worker_files.h"
#include <set>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace w = worker_files;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("fat_worker_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("fat_worker_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw std::invalid_argument("fat_worker_integer");
    return std::stoull(s);
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        throw std::invalid_argument("fat_worker_shape");
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            throw std::invalid_argument("fat_worker_shape");
}
V request(const FatSnapshotInput &input) {
    auto value = fat_snapshot_input_value(input);
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *p = input.fixture.find(key))
            value.put(key, *p);
    return V::object()
        .put("capture_epoch", number(input.capture_epoch))
        .put("policy", V::object())
        .put("provider_input", std::move(value));
}
json::Limits reply_limits() {
    json::Limits l;
    l.bytes = 32768;
    l.values = 512;
    l.depth = 12;
    l.string_bytes = 32768;
    return l;
}
V publication(const char *status, std::size_t bytes, const V &digest, const V &diagnostic = V{}) {
    return V::object()
        .put("schema", V::string("org.disked.fat-worker-publication/1"))
        .put("status", V::string(status))
        .put("payload_bytes", number(bytes))
        .put("sha256", digest)
        .put("diagnostic", diagnostic)
        .put("claims", fat_snapshot_claims());
}
V unavailable(const std::string &code, std::uint32_t platform = 0) {
    return publication(
        "unavailable", 0, V{},
        V::object().put("code", V::string(code)).put("platform_code", number(platform)));
}
V frame(const V &value, const FatSnapshotInput &input, const void *view) {
    exact(value, {"schema", "status", "payload_bytes", "sha256", "diagnostic", "claims"});
    if (text(value, "schema") != "org.disked.fat-worker-publication/1" ||
        json::dump(field(value, "claims")) != json::dump(fat_snapshot_claims()))
        throw std::invalid_argument("fat_worker_claims");
    if (text(value, "status") == "unavailable") {
        const auto &error = field(value, "diagnostic");
        exact(error, {"code", "platform_code"});
        const auto code = text(error, "code");
        if (integer(value, "payload_bytes") || field(value, "sha256").kind != V::Kind::null ||
            code.empty() || code.size() > 128 || code.find('\0') != code.npos ||
            !json::valid_utf8(code) || integer(error, "platform_code") > 0xffffffffULL)
            throw std::invalid_argument("fat_worker_failure");
        return V{};
    }
    if (text(value, "status") != "captured" || field(value, "diagnostic").kind != V::Kind::null)
        throw std::invalid_argument("fat_worker_status");
    const auto bytes = integer(value, "payload_bytes");
    if (!view || !bytes || bytes > fat_snapshot_payload_bytes)
        throw std::invalid_argument("fat_worker_payload");
    const std::string copied(static_cast<const char *>(view), static_cast<std::size_t>(bytes));
    if (text(value, "sha256") != "sha256:" + w::hash(copied))
        throw std::invalid_argument("fat_worker_payload_digest");
    auto out = json::parse(copied, fat_snapshot_json_limits());
    verify_fat_snapshot_frame(out, input);
    return out;
}
ObservationWorkerProfile profile(const void *view = nullptr) {
    ObservationWorkerProfile p;
    p.prefix = "fat";
    p.scope = "ordinary-local-file-fat";
    p.input_schema = "org.disked.fat-worker-input/1";
    p.reply_schema = "org.disked.fat-worker-reply/1";
    p.observation_schema = "org.disked.fat-worker-observation/1";
    p.role = L"__disked_fat_reader_worker";
    p.attempt_prefix = "fat-attempt:";
    p.records_field = "sha256";
    p.input_mapping_bytes = 131072;
    p.input_limits.bytes = 131068;
    p.input_limits.values = 16384;
    p.input_limits.depth = 16;
    p.input_limits.string_bytes = 32768;
    p.provider_limits = p.input_limits;
    p.reply_limits = reply_limits();
    p.payload_bytes = fat_snapshot_payload_bytes;
    p.validate_request = [](const V &h) { fat_snapshot_input_from(h); };
    p.validate_result = [view](const V &value, const V &h) {
        frame(value, fat_snapshot_input_from(h), view);
    };
    return p;
}
struct WritableView {
    void *value = nullptr;
    explicit WritableView(HANDLE mapping) {
        value = MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, fat_snapshot_payload_bytes);
        if (!value)
            w::fail("fat_worker_mapping");
    }
    ~WritableView() {
        if (value)
            UnmapViewOfFile(value);
    }
    WritableView(const WritableView &) = delete;
    WritableView &operator=(const WritableView &) = delete;
};
} // namespace
struct FatWorker::Impl {
    FatSnapshotInput input;
    w::Handle mapping;
    void *view = nullptr;
    std::unique_ptr<ObservationWorker> worker;
    explicit Impl(FatSnapshotInput value) : input(std::move(value)) {
    }
    ~Impl() {
        worker.reset();
        if (view)
            UnmapViewOfFile(view);
    }
};
FatWorker::FatWorker(std::unique_ptr<Impl> p) : impl_(std::move(p)) {
}
FatWorker::~FatWorker() = default;
std::unique_ptr<FatWorker> FatWorker::prepare(const FatSnapshotInput &input) {
    validate_fat_snapshot_input(input);
    std::unique_ptr<Impl> p(new Impl(input));
    w::Security security;
    auto attributes = security.attributes;
    p->mapping =
        w::Handle(CreateFileMappingW(INVALID_HANDLE_VALUE, &attributes, PAGE_READWRITE, 0,
                                     static_cast<DWORD>(fat_snapshot_payload_bytes), nullptr));
    if (!p->mapping.valid())
        w::fail("fat_worker_mapping");
    p->view = MapViewOfFile(p->mapping.value, FILE_MAP_READ, 0, 0, fat_snapshot_payload_bytes);
    if (!p->view)
        w::fail("fat_worker_mapping");
    p->worker = ObservationWorker::prepare(request(input), profile(p->view), p->mapping.value);
    return std::unique_ptr<FatWorker>(new FatWorker(std::move(p)));
}
void FatWorker::launch() {
    impl_->worker->launch();
}
void FatWorker::release() {
    impl_->worker->release();
}
void FatWorker::cancel() {
    impl_->worker->cancel();
}
bool FatWorker::never_launched() const {
    return impl_->worker->never_launched();
}
bool FatWorker::wait_entered(DWORD n) {
    return impl_->worker->wait_entered(n);
}
V FatWorker::observe(DWORD n) {
    auto observed = impl_->worker->observe(n);
    if (text(observed, "status") == "completed") {
        try {
            const auto captured = frame(field(observed, "result"), impl_->input, impl_->view);
            if (captured.kind != V::Kind::null) {
                const auto &process = field(observed, "worker");
                if (integer(captured, "process_id") != integer(process, "pid") ||
                    integer(captured, "process_created") != integer(process, "created"))
                    throw std::invalid_argument("fat_worker_capture_process");
            }
        } catch (const std::exception &error) {
            observed.put("status", V::string("unknown"))
                .put("diagnostic", V::string(error.what()))
                .put("result", V{});
        }
    }
    return observed;
}
V FatWorker::retire(DWORD n) {
    impl_->worker->retire(n);
    return observe();
}
std::shared_ptr<const FatFileSnapshot> FatWorker::snapshot(bool retain_frame) {
    const auto observed = observe();
    if (text(observed, "status") != "completed")
        return {};
    auto captured = frame(field(observed, "result"), impl_->input, impl_->view);
    if (captured.kind == V::Kind::null)
        return {};
    auto context = V::object();
    for (const auto key : {"attempt_id", "observer_epoch", "worker_epoch", "request_digest",
                           "code_sha256", "capture_epoch"})
        context.put(key, field(observed, key));
    const auto &process = field(observed, "worker");
    context.put("pid", field(process, "pid"))
        .put("created", field(process, "created"))
        .put("frame_sha256", field(field(observed, "result"), "sha256"))
        .put("image_profile", V::string("ordinary-file-fat"));
    // C++14 does not sequence constructor arguments: copy result before moving frame.
    auto result=field(captured,"result");
    auto retained=retain_frame?std::move(captured):V{};
    return std::shared_ptr<const FatFileSnapshot>(
        new FatFileSnapshot(std::move(result), std::move(context), std::move(retained)));
}
int fat_worker_role(int argc, wchar_t **argv) {
    return observation_worker_role(
        argc, argv, profile(),
        PayloadObservationFactory([](const V &h, const std::function<void()> &notify,
                                     HANDLE handle) -> ObservationCollector {
            const auto input = fat_snapshot_input_from(h);
            auto view = std::make_shared<WritableView>(handle);
            notify();
            return [input, view](const std::function<bool()> &stop) {
                try {
#ifdef DISKED_FAT_WORKER_TESTING
                    const auto *f = input.fixture.find("worker_fault");
                    const auto fault = f ? f->text : "";
                    if (fault == "hang")
                        for (;;)
                            Sleep(10);
                    if (fault == "late")
                        Sleep(200);
                    if (const auto *c = input.fixture.find("capture_fault")) {
                        const wchar_t *name =
                            c->text == "verify_changed"     ? L"DISKED_FAT_TEST_VERIFY_CHANGED"
                            : c->text == "verify_error"     ? L"DISKED_FAT_TEST_VERIFY_ERROR"
                            : c->text == "metadata_changed" ? L"DISKED_FAT_TEST_METADATA_CHANGED"
                            : c->text == "read_error"       ? L"DISKED_FAT_TEST_CAPTURE_ERROR"
                            : c->text == "short_read"       ? L"DISKED_FAT_TEST_CAPTURE_SHORT"
                                                            : L"DISKED_FAT_TEST_OVERLAP_CHANGED";
                        if (!SetEnvironmentVariableW(name, L"1"))
                            throw std::runtime_error("fat_worker_test_environment");
                    }
#endif
                    auto captured = read_fat_snapshot_frame(input, stop);
#ifdef DISKED_FAT_WORKER_TESTING
                    if (fault == "result_changed")
                        captured.fields["result"].fields["observation"].fields["geometry"].put(
                            "bits", V::string("1"));
                    if (fault == "receipt_changed")
                        captured.fields["result"].fields["capture"].put("path",
                                                                        V::string("forged"));
                    if (fault == "process_changed") {
                        captured.put("process_id", V::string("1"));
                        const auto &result = field(captured, "result");
                        auto domain =
                            V::object()
                                .put("process", field(captured, "process_id"))
                                .put("process_created", field(captured, "process_created"))
                                .put("sequence",
                                     field(field(result, "observation"), "capture_epoch"))
                                .put("source", input.expected_source);
                        captured.fields["result"].fields["capture"].put(
                            "capture_domain", V::string("sha256:" + w::hash(json::dump(domain))));
                    }
                    if (fault == "domain_changed")
                        captured.fields["result"].fields["capture"].put(
                            "capture_domain", V::string("sha256:" + std::string(64, '0')));
                    if (fault == "row_changed")
                        captured.fields["regions"].items[0].put("offset", V::string("1"));
#endif
                    const auto bytes = json::dump(captured, fat_snapshot_json_limits());
                    std::memcpy(view->value, bytes.data(), bytes.size());
                    MemoryBarrier();
                    auto value = publication("captured", bytes.size(),
                                             V::string("sha256:" + w::hash(bytes)));
#ifdef DISKED_FAT_WORKER_TESTING
                    if (fault == "payload_changed")
                        static_cast<char *>(view->value)[0] ^= 1;
                    if (fault == "claims")
                        value.fields["claims"].put("physical_admission", V::boolean_value(true));
#endif
                    return value;
                } catch (const local_file::Error &error) {
                    return unavailable(error.what(), error.platform_code);
                } catch (const std::exception &error) {
                    return unavailable(error.what());
                }
            };
        }));
}
} // namespace nt_inventory
} // namespace disked
