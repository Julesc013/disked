#include "fat_tree_extraction_worker.h"
#include "platform/windows/worker_files.h"
#include "providers/image/local_file.h"
#include <cstddef>
#include <cstring>
#include <mutex>
#include <set>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace w = worker_files;
namespace f = local_file;
constexpr std::size_t publication_bytes = 524288, grant_bytes = 16384;
struct alignas(8) Channel {
    volatile LONG publication_state, grant_state;
    DWORD publication_length, grant_length;
    volatile LONGLONG pulse;
    char publication_hash[64], grant_hash[64];
    char publication[publication_bytes], grant[grant_bytes];
};
static_assert(offsetof(Channel, pulse) % 8 == 0, "Windows interlocked 64-bit alignment");
struct View {
    void *value = nullptr;
    explicit View(HANDLE mapping) {
        value = MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, sizeof(Channel));
        if (!value)
            w::fail("fat_tree_writer_mapping");
    }
    ~View() {
        if (value)
            UnmapViewOfFile(value);
    }
    Channel *channel() const {
        return static_cast<Channel *>(value);
    }
};
[[noreturn]] void invalid(const char *code) {
    throw std::invalid_argument(code);
}
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        invalid("fat_tree_writer_shape");
    return *p;
}
void keys(const V &v, std::initializer_list<const char *> names) {
    if (v.kind != V::Kind::object || v.fields.size() != names.size())
        invalid("fat_tree_writer_shape");
    for (auto name : names)
        field(v, name);
}
std::string text(const V &v, const char *key) {
    const auto &x = field(v, key);
    if (x.kind != V::Kind::string)
        invalid("fat_tree_writer_shape");
    return x.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto value = text(v, key);
    if (!json::decimal_u64(value))
        invalid("fat_tree_writer_integer");
    return std::stoull(value);
}
bool boolean(const V &v, const char *key) {
    const auto &value = field(v, key);
    if (value.kind != V::Kind::boolean)
        invalid("fat_tree_writer_boolean");
    return value.boolean;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
json::Limits limits() {
    json::Limits l;
    l.bytes = publication_bytes;
    l.depth = 32;
    l.values = 65536;
    l.string_bytes = 32768;
    return l;
}
std::string encode(const V &v) {
    return json::dump(v, limits());
}
std::string digest(const V &v) {
    return "sha256:" + w::hash(encode(v));
}
FatTreeExtractionRequest request_from(const V &v) {
    keys(v, {"tree", "destination", "ledger", "metadata_policy", "budgets"});
    FatTreeExtractionRequest request;
    request.tree = fat_tree_input_from(field(v, "tree"));
    request.destination = text(v, "destination");
    request.ledger = text(v, "ledger");
    const auto &m = field(v, "metadata_policy");
    keys(m, {"name_selection", "unrepresentable_name", "oem_code_page", "time_interpretation",
             "utc_offset_minutes"});
    request.metadata.name_selection = text(m, "name_selection");
    request.metadata.unrepresentable_name = text(m, "unrepresentable_name");
    const auto cp = integer(m, "oem_code_page");
    if (cp > UINT32_MAX)
        invalid("fat_tree_writer_code_page");
    request.metadata.oem_code_page = static_cast<std::uint32_t>(cp);
    request.metadata.time_interpretation = text(m, "time_interpretation");
    const auto offset = text(m, "utc_offset_minutes");
    std::size_t used = 0;
    request.metadata.utc_offset_minutes = std::stoi(offset, &used);
    if (used != offset.size() || std::to_string(request.metadata.utc_offset_minutes) != offset)
        invalid("fat_tree_writer_offset");
    fat_metadata_policy_value(request.metadata);
    const auto &b = field(v, "budgets");
    keys(b, {"entries", "directories", "metadata_bytes", "pages", "content_bytes", "ledger_bytes"});
    const auto entries = integer(b, "entries"), dirs = integer(b, "directories"),
               metadata = integer(b, "metadata_bytes"), pages = integer(b, "pages");
    if (!entries || entries > 65536 || !dirs || dirs > 4096 || metadata < 16384 ||
        metadata > 67108864 || !pages || pages > 65536)
        invalid("fat_tree_writer_budget");
    request.entries = static_cast<std::size_t>(entries);
    request.directories = static_cast<std::size_t>(dirs);
    request.metadata_bytes = static_cast<std::size_t>(metadata);
    request.pages = static_cast<std::size_t>(pages);
    request.content_bytes = integer(b, "content_bytes");
    request.ledger_bytes = integer(b, "ledger_bytes");
    if (!request.content_bytes || request.content_bytes > 1099511627776ULL ||
        request.ledger_bytes < 1048576 || request.ledger_bytes > 1073741824)
        invalid("fat_tree_writer_budget");
    return request;
}
void fixture_valid(const V &v) {
    if (v.kind != V::Kind::object)
        invalid("fat_tree_writer_fixture");
#ifndef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
    if (!v.fields.empty())
        invalid("fat_tree_writer_fixture_not_compiled");
#else
    for (const auto &item : v.fields) {
        if (item.second.kind != V::Kind::string)
            invalid("fat_tree_writer_fixture");
        const auto &mode = item.second.text;
        if (item.first == "startup_fault" &&
            (mode == "before_spawn" || mode == "after_spawn" || mode == "after_spawn_alloc"))
            continue;
        if (item.first == "worker_fault" &&
            (mode == "prepare_hang" || mode == "execute_hang" || mode == "execute_wait_cancel" ||
             mode == "late" || mode == "outcome_hold" || mode == "definition_changed" ||
             mode == "owner_changed" || mode == "process_changed" || mode == "publication_digest" ||
             mode == "definition_rehashed" || mode == "exit_after_root" ||
             mode == "exit_after_completion"))
            continue;
        invalid("fat_tree_writer_fixture");
    }
#endif
}
void definition_shape(const V &definition, const FatTreeExtractionRequest &request) {
    keys(definition, {"schema", "selection", "prepared_input", "paths", "resources",
                      "metadata_policy", "budgets", "effects", "scratch_resources",
                      "recovery_resources", "source_consistency", "owner_accepted"});
    if (boolean(definition, "owner_accepted") ||
        text(definition, "effects") != "create-only-tree-and-independent-ordered-ledger" ||
        text(definition, "source_consistency") != "held-identity-and-read-agreement-not-atomic" ||
        field(definition, "scratch_resources").kind != V::Kind::array ||
        !field(definition, "scratch_resources").items.empty() ||
        field(definition, "recovery_resources").kind != V::Kind::array ||
        !field(definition, "recovery_resources").items.empty())
        invalid("fat_tree_writer_definition_effects");
    const auto &selection = field(definition, "selection"), &budgets = field(definition, "budgets");
    keys(selection, {"kind", "volume_offset", "volume_bytes", "fat_copy", "capture_epoch",
                     "preparation_binding", "preparation_context", "tree_digest", "pages",
                     "entries", "content_bytes"});
    keys(budgets, {"entries", "directories", "metadata_bytes", "pages", "content_bytes",
                   "ledger_bytes", "record_bytes", "code_bytes", "native_path_units"});
    if (integer(budgets, "entries") != request.entries ||
        integer(budgets, "directories") != request.directories ||
        integer(budgets, "metadata_bytes") != request.metadata_bytes ||
        integer(budgets, "pages") != request.pages ||
        integer(budgets, "content_bytes") != request.content_bytes ||
        integer(budgets, "ledger_bytes") != request.ledger_bytes ||
        integer(budgets, "record_bytes") != 262144 || integer(budgets, "code_bytes") != 8388608 ||
        integer(budgets, "native_path_units") != 240 ||
        text(selection, "kind") != "whole-live-tree" ||
        integer(selection, "entries") > request.entries || !integer(selection, "pages") ||
        integer(selection, "pages") > request.pages ||
        integer(selection, "content_bytes") > request.content_bytes)
        invalid("fat_tree_writer_definition_budget");
    const auto &resources = field(definition, "resources");
    keys(resources,
         {"source", "destination_tree", "metadata_ledger", "executable", "provider", "host"});
    const char *roles[] = {"source",     "destination_tree", "metadata_ledger",
                           "executable", "provider",         "host"};
    const char *access[] = {"read", "create-tree",    "create-append",
                            "read", "execute-linked", "declared-host-effects"};
    const char *verification[] = {"held-identity-and-region-agreement",
                                  "file-id-and-content-readback",
                                  "ordered-hash-chain",
                                  "identity-and-code-sha256",
                                  "same-linked-generation",
                                  "selected-host-profile"};
    for (std::size_t i = 0; i < 6; ++i) {
        const auto &resource = field(resources, roles[i]), &observed = field(resource, "observed"),
                   &aliases = field(resource, "aliases");
        keys(resource, {"identity", "epoch", "observed", "access", "footprint", "verification",
                        "aliases", "failure_domain"});
        const auto epoch = digest(observed), identity = "observed:" + epoch;
        if (text(resource, "epoch") != epoch || text(resource, "identity") != identity ||
            text(resource, "access") != access[i] ||
            text(resource, "verification") != verification[i] ||
            text(resource, "failure_domain").empty() || aliases.kind != V::Kind::array ||
            aliases.items.empty() || aliases.items.size() > 2 ||
            aliases.items[0].kind != V::Kind::string || aliases.items[0].text != identity)
            invalid("fat_tree_writer_definition_resource");
    }
    const auto &source = field(field(resources, "source"), "footprint");
    keys(source, {"kind", "start", "end"});
    if (text(source, "kind") != "byte-range" ||
        integer(source, "start") != request.tree.volume_offset ||
        integer(source, "end") != request.tree.volume_offset + request.tree.volume_bytes)
        invalid("fat_tree_writer_definition_footprint");
    const auto &destination = field(field(resources, "destination_tree"), "footprint");
    keys(destination, {"kind", "entries", "content_bytes"});
    if (text(destination, "kind") != "new-descendant-tree" ||
        integer(destination, "entries") != integer(selection, "entries") ||
        integer(destination, "content_bytes") != integer(selection, "content_bytes"))
        invalid("fat_tree_writer_definition_footprint");
    const auto &ledger = field(field(resources, "metadata_ledger"), "footprint");
    keys(ledger, {"kind", "bytes"});
    if (text(ledger, "kind") != "bounded-new-file" ||
        integer(ledger, "bytes") != request.ledger_bytes)
        invalid("fat_tree_writer_definition_footprint");
}
void outcome_shape(const V &value, const V &definition, const FatTreeExtractionRequest &request) {
    const auto status = text(value, "status");
    if (status != "complete" && status != "partial" && status != "partial_evidence_uncertain")
        invalid("fat_tree_writer_outcome_status");
    if (boolean(value, "source_writes") || boolean(value, "atomic_snapshot") ||
        boolean(value, "owner_accepted") || boolean(value, "contained_worker_qualified"))
        invalid("fat_tree_writer_outcome_claims");
    const auto verified = integer(value, "verified_bytes"),
               checkpointed = integer(value, "checkpointed_bytes");
    const auto files = integer(value, "files_complete"),
               dirs = integer(value, "directories_created");
    const auto &selection = field(definition, "selection");
    const auto entries = integer(selection, "entries"),
               expected = integer(selection, "content_bytes");
    if (checkpointed > verified || verified > expected || files > entries ||
        dirs > request.directories || integer(value, "ledger_bytes") > request.ledger_bytes ||
        integer(value, "ledger_records") > request.ledger_bytes ||
        integer(value, "platform_code") > UINT32_MAX)
        invalid("fat_tree_writer_outcome_counters");
    if (status == "complete" &&
        (verified != expected || checkpointed != expected || !dirs || files + dirs != entries + 1))
        invalid("fat_tree_writer_outcome_incomplete");
}
ObservationWorkerProfile profile() {
    ObservationWorkerProfile p;
    p.prefix = "fat_tree_writer";
    p.scope = "ordinary-local-file-fat-tree-extraction";
    p.input_schema = "org.disked.fat-tree-extraction-worker-input/1";
    p.reply_schema = "org.disked.fat-tree-extraction-worker-reply/1";
    p.observation_schema = "org.disked.fat-tree-extraction-worker-observation/1";
    p.role = L"__disked_fat_tree_extraction_worker";
    p.attempt_prefix = "fat-tree-write-attempt:";
    p.records_field = "publication_sha256";
    p.payload_bytes = sizeof(Channel);
    p.compiled_effects_capable = true;
    p.input_mapping_bytes = 65536;
    p.input_limits = limits();
    p.input_limits.bytes = 65532;
    p.provider_limits = p.input_limits;
    p.reply_limits = p.input_limits;
    p.validate_request = [](const V &header) {
        const auto &input = field(header, "provider_input");
        if (input.find("startup_fault")) {
            keys(input, {"request", "fixture", "startup_fault"});
            if (text(input, "startup_fault") != text(field(input, "fixture"), "startup_fault"))
                invalid("fat_tree_writer_startup_fixture");
        } else
            keys(input, {"request", "fixture"});
        fixture_valid(field(input, "fixture"));
        const auto request = request_from(field(input, "request"));
        if (integer(header, "capture_epoch") != request.tree.capture_epoch)
            invalid("fat_tree_writer_epoch");
    };
    p.validate_result = [](const V &value, const V &) {
        keys(value, {"schema", "phase", "publication_sha256"});
        if (text(value, "schema") != "org.disked.fat-tree-extraction-worker-final/1")
            invalid("fat_tree_writer_final");
        const auto phase = text(value, "phase");
        if (phase != "outcome" && phase != "cancelled" && phase != "unavailable")
            invalid("fat_tree_writer_final");
        const auto hash = text(value, "publication_sha256");
        if (hash.size() != 71 || hash.substr(0, 7) != "sha256:" ||
            hash.find_first_not_of("0123456789abcdef", 7) != hash.npos)
            invalid("fat_tree_writer_final");
    };
    return p;
}
V owner(const V &header) {
    auto value = V::object();
    for (const char *key : {"host_id", "code_sha256", "capture_epoch", "observer_epoch",
                            "worker_epoch", "attempt_id"})
        value.put(key, field(header, key));
    return value.put("request_digest",
                     V::string("sha256:" + w::hash(json::dump(header, profile().input_limits))));
}
V final(const char *phase, const std::string &publication) {
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-extraction-worker-final/1"))
        .put("phase", V::string(phase))
        .put("publication_sha256", V::string(publication));
}
std::string publish(Channel *channel, V envelope, const std::function<bool()> &stop) {
    while (InterlockedCompareExchange(&channel->publication_state, 0, 0) != 0) {
        if (stop())
            invalid("fat_tree_writer_cancelled");
        Sleep(1);
    }
    const auto bytes = encode(envelope), hash = w::hash(bytes);
    if (bytes.empty() || bytes.size() > publication_bytes)
        invalid("fat_tree_writer_publication_limit");
    channel->publication_length = static_cast<DWORD>(bytes.size());
    std::memcpy(channel->publication, bytes.data(), bytes.size());
    std::memcpy(channel->publication_hash, hash.data(), 64);
    MemoryBarrier();
    InterlockedExchange(&channel->publication_state, 1);
    return "sha256:" + hash;
}
V take_grant(Channel *channel, const std::function<bool()> &stop) {
    for (;;) {
        if (stop())
            invalid("fat_tree_writer_cancelled");
        if (InterlockedCompareExchange(&channel->grant_state, 2, 1) == 1)
            break;
        Sleep(1);
    }
    MemoryBarrier();
    const auto length = channel->grant_length;
    if (!length || length > grant_bytes)
        invalid("fat_tree_writer_grant_publication");
    const std::string bytes(channel->grant, length), hash(channel->grant_hash, 64);
    MemoryBarrier();
    if (channel->grant_state != 2 || channel->grant_length != length || w::hash(bytes) != hash)
        invalid("fat_tree_writer_grant_digest");
    return json::parse(bytes, limits());
}
struct Dependency {
    std::wstring path;
    std::vector<f::Handle> parents;
    V generations;
    f::Handle source;
    V metadata;
    Dependency(const std::string &name, bool read_source)
        : path(f::path_for(name)), parents(f::pin_parents(path)),
          generations(f::parent_generations(parents)) {
        if (read_source) {
            source = f::Handle(
                CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            if (source.value == INVALID_HANDLE_VALUE)
                w::fail("fat_tree_writer_source_open");
            f::ordinary(source.value, false);
            f::bind_path(source.value, path);
            metadata = f::metadata(source.value).value;
        }
    }
    void check() const {
        f::check_parents(path, parents, generations);
        if (source.value != INVALID_HANDLE_VALUE) {
            f::bind_path(source.value, path);
            if (encode(f::metadata(source.value).value) != encode(metadata))
                invalid("fat_tree_writer_source_changed");
        }
    }
};
std::mutex retained_mutex;
} // namespace

V fat_tree_extraction_worker_request(const FatTreeExtractionRequest &r) {
    return V::object()
        .put("tree", fat_tree_input_value(r.tree))
        .put("destination", V::string(r.destination))
        .put("ledger", V::string(r.ledger))
        .put("metadata_policy", fat_metadata_policy_value(r.metadata))
        .put("budgets", V::object()
                            .put("entries", number(r.entries))
                            .put("directories", number(r.directories))
                            .put("metadata_bytes", number(r.metadata_bytes))
                            .put("pages", number(r.pages))
                            .put("content_bytes", number(r.content_bytes))
                            .put("ledger_bytes", number(r.ledger_bytes)));
}
struct FatTreeExtractionWorker::Impl {
    FatTreeExtractionRequest request;
    V fixture;
    Dependency source, destination, ledger;
    w::Handle mapping;
    std::unique_ptr<View> view;
    std::unique_ptr<ObservationWorker> worker;
    std::shared_ptr<const FatTreeExtractionPreparation> preparation;
    V outcome;
    std::string publication_digest, phase, diagnostic;
    bool grant_sent = false, failed = false;
    Impl *retained_next = nullptr;
    static Impl *retained_head;
    Impl(const FatTreeExtractionRequest &r, V controls)
        : request(r), fixture(std::move(controls)), source(r.tree.path, true),
          destination(r.destination, false), ledger(r.ledger, false) {
        if (request.tree.expected_source.kind != V::Kind::null &&
            encode(request.tree.expected_source) != encode(source.metadata))
            invalid("fat_tree_writer_source_changed");
        request.tree.path = f::utf8(source.path);
        request.tree.expected_source = source.metadata;
        request.destination = f::utf8(destination.path);
        request.ledger = f::utf8(ledger.path);
    }
    bool exited() {
        return worker->never_launched() ||
               text(field(worker->observe(), "worker"), "observation") == "exited";
    }
    void check() const {
        source.check();
        destination.check();
        ledger.check();
    }
};
FatTreeExtractionWorker::Impl *FatTreeExtractionWorker::Impl::retained_head = nullptr;
FatTreeExtractionWorker::FatTreeExtractionWorker(std::unique_ptr<Impl> p) : impl_(std::move(p)) {
}
FatTreeExtractionWorker::~FatTreeExtractionWorker() {
    if (!impl_)
        return;
    bool exited = false;
    try {
        exited = impl_->exited();
        if (!exited) {
            impl_->worker->cancel();
            impl_->worker->retire(2000);
            exited = impl_->exited();
        }
    } catch (...) {
    }
    if (!exited) {
        std::lock_guard<std::mutex> guard(retained_mutex);
        auto *p = impl_.release();
        p->retained_next = Impl::retained_head;
        Impl::retained_head = p;
    }
}
std::size_t FatTreeExtractionWorker::reap_retained() {
    std::lock_guard<std::mutex> guard(retained_mutex);
    std::size_t retained = 0;
    auto **link = &Impl::retained_head;
    while (*link) {
        auto *p = *link;
        bool exited = false;
        try {
            exited = p->exited();
        } catch (...) {
        }
        if (exited) {
            *link = p->retained_next;
            delete p;
        } else {
            ++retained;
            link = &p->retained_next;
        }
    }
    return retained;
}
std::unique_ptr<FatTreeExtractionWorker>
FatTreeExtractionWorker::prepare(const FatTreeExtractionRequest &r, const V &fixture) {
    fixture_valid(fixture);
    const auto checked = request_from(fat_tree_extraction_worker_request(r));
    reap_retained();
    std::unique_ptr<Impl> p(new Impl(checked, fixture));
    w::Security security;
    auto attributes = security.attributes;
    p->mapping = w::Handle(CreateFileMappingW(INVALID_HANDLE_VALUE, &attributes, PAGE_READWRITE, 0,
                                              sizeof(Channel), nullptr));
    if (!p->mapping.valid())
        w::fail("fat_tree_writer_mapping_create");
    p->view.reset(new View(p->mapping.value));
    auto input = V::object()
                     .put("request", fat_tree_extraction_worker_request(p->request))
                     .put("fixture", fixture);
    // The generic host's compiled startup fixture reads only this exact field.
    if (const auto *f = fixture.find("startup_fault"))
        input.put("startup_fault", *f);
    auto request = V::object()
                       .put("capture_epoch", number(r.tree.capture_epoch))
                       .put("policy", V::object())
                       .put("provider_input", input);
    p->worker = ObservationWorker::prepare(request, profile(), p->mapping.value);
    return std::unique_ptr<FatTreeExtractionWorker>(new FatTreeExtractionWorker(std::move(p)));
}
void FatTreeExtractionWorker::launch() {
    impl_->check();
    impl_->worker->launch();
}
void FatTreeExtractionWorker::release() {
    impl_->worker->release();
}
void FatTreeExtractionWorker::cancel() {
    impl_->worker->cancel();
}
bool FatTreeExtractionWorker::never_launched() const {
    return impl_->worker->never_launched();
}
std::shared_ptr<const FatTreeExtractionPreparation> FatTreeExtractionWorker::prepared() const {
    return impl_->preparation;
}
V FatTreeExtractionWorker::observe(DWORD wait_ms) {
    auto &p = *impl_;
    auto observed = p.worker->observe(wait_ms);
    auto *channel = p.view->channel();
    if (!p.failed && InterlockedCompareExchange(&channel->publication_state, 2, 1) == 1) {
        try {
            MemoryBarrier();
            const auto length = channel->publication_length;
            if (!length || length > publication_bytes)
                invalid("fat_tree_writer_publication");
            const std::string bytes(channel->publication, length),
                hash(channel->publication_hash, 64);
            MemoryBarrier();
            if (channel->publication_state != 2 || channel->publication_length != length ||
                w::hash(bytes) != hash)
                invalid("fat_tree_writer_publication_digest");
            const auto envelope = json::parse(bytes, limits());
            keys(envelope, {"schema", "owner", "process", "phase", "value"});
            if (text(envelope, "schema") != "org.disked.fat-tree-extraction-envelope/1" ||
                encode(field(envelope, "owner")) != encode(owner(p.worker->binding())))
                invalid("fat_tree_writer_publication_owner");
            const auto &process = field(envelope, "process"), &actual = field(observed, "worker");
            keys(process, {"pid", "created"});
            if (text(process, "pid") != text(actual, "pid") ||
                text(process, "created") != text(actual, "created"))
                invalid("fat_tree_writer_publication_process");
            const auto phase = text(envelope, "phase");
            const auto &value = field(envelope, "value");
            if (phase == "prepared") {
                if (p.preparation || p.grant_sent)
                    invalid("fat_tree_writer_preparation_reused");
                keys(value, {"definition", "definition_digest"});
                const auto &definition = field(value, "definition");
                definition_shape(definition, p.request);
                const auto definition_hash =
                    "sha256:" + w::hash("disked:fat-tree-extraction-plan:1\n" + encode(definition));
                if (text(value, "definition_digest") != definition_hash ||
                    text(definition, "schema") !=
                        "org.disked.fat-tree-extraction-plan-prototype/1" ||
                    encode(field(definition, "prepared_input")) !=
                        encode(fat_tree_input_value(p.request.tree)) ||
                    encode(field(definition, "metadata_policy")) !=
                        encode(fat_metadata_policy_value(p.request.metadata)))
                    invalid("fat_tree_writer_definition");
                const auto &paths = field(definition, "paths");
                if (text(paths, "source") != p.request.tree.path ||
                    text(paths, "destination") != p.request.destination ||
                    text(paths, "ledger") != p.request.ledger)
                    invalid("fat_tree_writer_definition_paths");
                const auto &resources = field(definition, "resources"),
                           &selection = field(definition, "selection");
                if (text(field(field(resources, "executable"), "observed"), "sha256") !=
                        "sha256:" + text(p.worker->binding(), "code_sha256") ||
                    encode(field(field(field(resources, "source"), "observed"), "file")) !=
                        encode(p.source.metadata) ||
                    integer(selection, "volume_offset") != p.request.tree.volume_offset ||
                    integer(selection, "volume_bytes") != p.request.tree.volume_bytes ||
                    integer(selection, "fat_copy") != p.request.tree.fat_copy ||
                    integer(selection, "capture_epoch") != p.request.tree.capture_epoch)
                    invalid("fat_tree_writer_definition_binding");
                if (encode(field(field(field(resources, "source"), "observed"), "parents")) !=
                        encode(p.source.generations) ||
                    encode(field(field(field(resources, "destination_tree"), "observed"),
                                 "parents")) != encode(p.destination.generations) ||
                    encode(field(field(field(resources, "metadata_ledger"), "observed"),
                                 "parents")) != encode(p.ledger.generations))
                    invalid("fat_tree_writer_parent_binding");
                const auto &capture = field(selection, "preparation_binding"),
                           &capture_context = field(selection, "preparation_context");
                if (text(capture_context, "process_id") != text(actual, "pid") ||
                    text(capture_context, "process_created") != text(actual, "created") ||
                    encode(capture) != encode(fat_tree_binding_value(
                                           fat_tree_binding(p.request.tree, capture_context))))
                    invalid("fat_tree_writer_capture_binding");
                if (text(capture, "capture_epoch") != text(p.worker->binding(), "capture_epoch"))
                    invalid("fat_tree_writer_definition_epoch");
                p.check();
                p.preparation.reset(new FatTreeExtractionPreparation(
                    definition, field(envelope, "owner"), definition_hash, "sha256:" + hash));
            } else if (phase == "outcome") {
                if (!p.preparation || !p.grant_sent || p.outcome.kind != V::Kind::null ||
                    text(value, "schema") != "org.disked.fat-tree-extraction-outcome-prototype/1" ||
                    text(value, "definition_digest") != p.preparation->digest() ||
                    text(value, "attempt_id") != text(p.worker->binding(), "attempt_id"))
                    invalid("fat_tree_writer_outcome_binding");
                p.outcome = value;
                outcome_shape(p.outcome, p.preparation->definition(), p.request);
            } else if (phase != "cancelled" && phase != "unavailable")
                invalid("fat_tree_writer_phase");
            p.phase = phase;
            p.publication_digest = "sha256:" + hash;
            MemoryBarrier();
            InterlockedExchange(&channel->publication_state, 0);
        } catch (const std::exception &error) {
            p.failed = true;
            p.diagnostic = error.what();
            p.worker->cancel();
        }
    }
    if (!p.failed && text(observed, "status") == "completed") {
        const auto &final = field(observed, "result");
        if (p.publication_digest.empty() ||
            text(final, "publication_sha256") != p.publication_digest ||
            text(final, "phase") != p.phase) {
            p.failed = true;
            p.diagnostic = "fat_tree_writer_final_publication";
            p.worker->cancel();
        }
    }
    const auto pulse = InterlockedCompareExchange64(&channel->pulse, 0, 0);
    observed
        .put("preparation", p.preparation ? V::object().put("definition_digest",
                                                            V::string(p.preparation->digest()))
                                          : V{})
        .put("grant_sent", V::boolean_value(p.grant_sent))
        .put("effects_possible", V::boolean_value(p.grant_sent))
        .put("phase", p.phase.empty() ? V{} : V::string(p.phase))
        .put("progress_pulse", number(static_cast<std::uint64_t>(pulse)))
        .put("outcome", p.failed ? V{} : p.outcome)
        .put("dependencies_retained", V::boolean_value(!p.exited()));
    if (p.failed)
        observed.put("status", V::string("unknown"))
            .put("diagnostic", V::string(p.diagnostic))
            .put("result", V{});
    else if (p.preparation && !p.grant_sent && p.phase == "prepared" &&
             text(field(observed, "worker"), "observation") == "running")
        observed.put("status", V::string("awaiting_grant"));
    return observed;
}
void FatTreeExtractionWorker::grant(const FatTreeExtractionGrant &grant) {
    auto &p = *impl_;
    const auto state = observe();
    if (p.failed || !p.preparation || p.grant_sent || p.phase != "prepared" ||
        boolean(state, "cancellation_requested") || p.exited() ||
        grant.definition_digest != p.preparation->digest() || !grant.source_read ||
        !grant.destination_write || !grant.ledger_write || !grant.host_effects)
        invalid("fat_tree_writer_grant");
    p.check();
    auto envelope =
        V::object()
            .put("schema", V::string("org.disked.fat-tree-extraction-grant-envelope/1"))
            .put("owner", p.preparation->owner())
            .put("preparation_sha256", V::string(p.preparation->publication_digest_))
            .put("grant", V::object()
                              .put("definition_digest", V::string(grant.definition_digest))
                              .put("source_read", V::boolean_value(grant.source_read))
                              .put("destination_write", V::boolean_value(grant.destination_write))
                              .put("ledger_write", V::boolean_value(grant.ledger_write))
                              .put("host_effects", V::boolean_value(grant.host_effects)));
    const auto bytes = encode(envelope), hash = w::hash(bytes);
    auto *channel = p.view->channel();
    if (bytes.size() > grant_bytes || InterlockedCompareExchange(&channel->grant_state, 0, 0) != 0)
        invalid("fat_tree_writer_grant_state");
    channel->grant_length = static_cast<DWORD>(bytes.size());
    std::memcpy(channel->grant, bytes.data(), bytes.size());
    std::memcpy(channel->grant_hash, hash.data(), 64);
    p.grant_sent = true;
    MemoryBarrier();
    InterlockedExchange(&channel->grant_state, 1);
}
V FatTreeExtractionWorker::retire(DWORD wait_ms) {
    impl_->worker->retire(wait_ms);
    return observe();
}

int fat_tree_extraction_worker_role(int argc, wchar_t **argv) {
    return observation_worker_role(
        argc, argv, profile(),
        PayloadObservationFactory([](const V &header, const std::function<void()> &notify,
                                     HANDLE mapping) -> ObservationCollector {
            const auto &input = field(header, "provider_input");
            const auto request = request_from(field(input, "request"));
            const auto fixture = field(input, "fixture"), launch_owner = owner(header);
            auto view = std::make_shared<View>(mapping);
            notify();
            return [request, fixture, launch_owner, view](const std::function<bool()> &stop) {
                auto *channel = view->channel();
                std::string last;
                const auto process =
                    V::object()
                        .put("pid", number(GetCurrentProcessId()))
                        .put("created", V::string(w::process_created(GetCurrentProcess())));
                auto envelope = [&](const char *phase, V value) {
                    return V::object()
                        .put("schema", V::string("org.disked.fat-tree-extraction-envelope/1"))
                        .put("owner", launch_owner)
                        .put("process", process)
                        .put("phase", V::string(phase))
                        .put("value", std::move(value));
                };
                const auto *f = fixture.find("worker_fault");
                const auto fault = f ? f->text : "";
                try {
#ifdef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
                    if (fault == "prepare_hang")
                        for (;;)
                            Sleep(10);
                    if (fault == "late")
                        Sleep(250);
#endif
                    FatTreeExtraction operation(
                        request, stop, [channel] { InterlockedIncrement64(&channel->pulse); });
                    auto prepared = envelope(
                        "prepared", V::object()
                                        .put("definition", operation.definition())
                                        .put("definition_digest", V::string(operation.digest())));
#ifdef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
                    if (fault == "definition_changed")
                        prepared.fields.at("value")
                            .fields.at("definition")
                            .fields.at("selection")
                            .put("fat_copy", number(1));
                    if (fault == "definition_rehashed") {
                        auto &definition = prepared.fields.at("value").fields.at("definition");
                        definition.fields.at("budgets").put("entries", number(request.entries + 1));
                        prepared.fields.at("value").put(
                            "definition_digest",
                            V::string("sha256:" + w::hash("disked:fat-tree-extraction-plan:1\n" +
                                                          encode(definition))));
                    }
                    if (fault == "owner_changed")
                        prepared.fields.at("owner").put("worker_epoch", V::string("stale"));
                    if (fault == "process_changed")
                        prepared.fields.at("process").put("pid", number(1));
#endif
                    last = publish(channel, std::move(prepared), stop);
#ifdef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
                    if (fault == "publication_digest")
                        channel->publication_hash[0] = 'x';
#endif
                    const auto grant = take_grant(channel, stop);
                    keys(grant, {"schema", "owner", "preparation_sha256", "grant"});
                    if (text(grant, "schema") !=
                            "org.disked.fat-tree-extraction-grant-envelope/1" ||
                        encode(field(grant, "owner")) != encode(launch_owner) ||
                        text(grant, "preparation_sha256") != last)
                        invalid("fat_tree_writer_grant_owner");
                    const auto &value = field(grant, "grant");
                    keys(value, {"definition_digest", "source_read", "destination_write",
                                 "ledger_write", "host_effects"});
                    FatTreeExtractionGrant effects{
                        text(value, "definition_digest"), boolean(value, "source_read"),
                        boolean(value, "destination_write"), boolean(value, "ledger_write"),
                        boolean(value, "host_effects")};
                    FatTreeExtractionHooks hooks;
                    hooks.attempt_id = text(launch_owner, "attempt_id");
                    hooks.stop = stop;
                    hooks.boundary = [channel, fault, stop](const char *boundary) {
                        InterlockedIncrement64(&channel->pulse);
#ifdef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
                        if (fault == "execute_hang" && std::strcmp(boundary, "root_created") == 0)
                            for (;;)
                                Sleep(10);
                        if (fault == "execute_wait_cancel" &&
                            std::strcmp(boundary, "root_created") == 0)
                            while (!stop())
                                Sleep(1);
                        if (fault == "exit_after_root" &&
                            std::strcmp(boundary, "root_created") == 0)
                            ExitProcess(93);
                        if (fault == "exit_after_completion" &&
                            std::strcmp(boundary, "complete_flushed") == 0)
                            ExitProcess(93);
#else
                        (void)boundary;
                        (void)fault;
#endif
                    };
                    const auto result = operation.execute(effects, hooks);
                    last = publish(channel, envelope("outcome", result), [] { return false; });
#ifdef DISKED_FAT_TREE_EXTRACTION_WORKER_TESTING
                    if (fault == "outcome_hold")
                        Sleep(500);
#endif
                    return final("outcome", last);
                } catch (const std::exception &error) {
                    const bool cancelled = stop();
                    try {
                        last = publish(
                            channel,
                            envelope(cancelled ? "cancelled" : "unavailable",
                                     V::object().put("diagnostic", V::string(error.what()))),
                            [] { return false; });
                        return final(cancelled ? "cancelled" : "unavailable", last);
                    } catch (...) {
                        return final("unavailable", "sha256:" + std::string(64, '0'));
                    }
                }
            };
        }));
}
} // namespace nt_inventory
} // namespace disked
