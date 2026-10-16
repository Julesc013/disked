#include "fat_tree_store.h"
#include "platform/windows/worker_files.h"
#include <algorithm>

namespace disked {
namespace nt_inventory {
namespace {
namespace w = worker_files;
namespace f = local_file;
using V = json::Value;
const wchar_t *const names[] = {L"recursive-request.json", L"recursive-cancel",
                                L"recursive-state.ndjson"};
[[noreturn]] void fail(const char *code, DWORD error = 0) {
    throw FatTreeStoreError(code, error);
}
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        fail("fat_tree_store_shape");
    return *p;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hash(const std::string &s) {
    return "sha256:" + w::hash(s);
}
std::string encode(const V &v, std::size_t max = 524288) {
    auto l = fat_tree_review_limits();
    l.bytes = max;
    return json::dump(v, l);
}
V file_alias(const V &file) {
    return V::object()
        .put("volume_id", field(file, "volume_id"))
        .put("file_id", field(file, "file_id"));
}
} // namespace
struct FatTreeStore::Impl {
    w::Directory directory;
    w::Security security;
    V observed, binding, child_ids, writer;
    w::Handle files[3];
    std::string operation, review_digest, previous = "sha256:" + std::string(64, '0');
    std::size_t bytes = 0, records = 0;
    bool effects = false, ready = false, uncertain = false;
    Impl(const std::string &path, const FatTreeExtractionRequest &request) : directory(path) {
        wchar_t filesystem[32]{};
        if (!GetVolumeInformationByHandleW(directory.pinned.back().value, nullptr, 0, nullptr,
                                           nullptr, nullptr, filesystem, 32))
            fail("fat_tree_store_filesystem", GetLastError());
        if (std::wcscmp(filesystem, L"NTFS"))
            fail("fat_tree_store_ntfs_required");
        const auto generation = f::generation(directory.pinned.back().value, true);
        observed = V::object()
                       .put("file", generation)
                       .put("parents", directory.generations)
                       .put("path", V::string(f::utf8(directory.path)));
        auto aliases = V::array();
        const auto epoch = hash(encode(observed));
        aliases.items.push_back(V::string("observed:" + epoch));
        aliases.items.push_back(V::string("file:" + hash(encode(file_alias(generation)))));
        auto children = V::array();
        for (const auto *name : names)
            children.items.push_back(V::string(w::narrow(name)));
        binding = V::object()
                      .put("identity", V::string("observed:" + epoch))
                      .put("epoch", V::string(epoch))
                      .put("observed", observed)
                      .put("access", V::string("create-operation-state"))
                      .put("footprint", V::object()
                                            .put("kind", V::string("finite-control-files"))
                                            .put("children", children)
                                            .put("record_bytes", number(16384))
                                            .put("total_bytes", number(1048576))
                                            .put("records", number(64)))
                      .put("verification", V::string("identity-epoch-and-ordered-state-history"))
                      .put("aliases", aliases)
                      .put("failure_domain", V::string("observed-file-volume:" +
                                                       field(generation, "volume_id").text));
        for (const auto &input : {request.tree.path, request.destination, request.ledger}) {
            const auto target = f::path_for(input);
            auto pinned = f::pin_parents(target);
            if (encode(f::generation(pinned.back().value, true)) != encode(generation))
                continue;
            const auto leaf = target.substr(target.rfind(L'\\') + 1);
            for (const auto *name : names)
                if (CompareStringOrdinal(leaf.c_str(), -1, name, -1, TRUE) == CSTR_EQUAL)
                    fail("fat_tree_store_resource_alias");
        }
        unused();
    }
    void check() const {
        directory.check();
        if (encode(f::generation(directory.pinned.back().value, true)) !=
            encode(field(observed, "file")))
            fail("fat_tree_store_changed");
        for (std::size_t i = 0; i < 3; ++i)
            if (files[i].valid()) {
                f::ordinary(files[i].value, false);
                f::bind_path(files[i].value, directory.child(names[i]));
                const auto info = w::file_info(files[i].value);
                if (info.nNumberOfLinks != 1 ||
                    encode(f::generation(files[i].value, false)) != encode(child_ids.items[i]))
                    fail("fat_tree_store_child_changed");
            }
    }
    void unused() const {
        check();
        for (const auto *name : names) {
            if (GetFileAttributesW(directory.child(name).c_str()) != INVALID_FILE_ATTRIBUTES)
                fail("fat_tree_store_reserved_exists");
            const auto error = GetLastError();
            if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND)
                fail("fat_tree_store_child_observation", error);
        }
        check();
    }
    void append(const char *phase, const V &worker) {
        if (uncertain)
            fail("fat_tree_store_uncertain");
        if (!ready)
            fail("fat_tree_store_not_reserved");
        check();
        FILETIME now{};
        GetSystemTimeAsFileTime(&now);
        const auto value =
            V::object()
                .put("schema", V::string("org.disked.fat-tree-state-record-prototype/1"))
                .put("operation_id", V::string(operation))
                .put("review_digest", V::string(review_digest))
                .put("sequence", number(records))
                .put("previous", V::string(previous))
                .put("payload", V::object()
                                    .put("phase", V::string(phase))
                                    .put("observed_at", number(w::file_time(now)))
                                    .put("worker", worker));
        const auto text = encode(value, 16383) + "\n";
        if (records >= 64 || text.size() > 1048576 - bytes)
            fail("fat_tree_store_budget");
        LARGE_INTEGER end{};
        if (!SetFilePointerEx(files[2].value, end, nullptr, FILE_END))
            fail("fat_tree_store_seek", GetLastError());
        try {
            w::write_file(files[2].value, text, "fat_tree_state");
        } catch (...) {
            uncertain = true;
            throw;
        }
        previous = hash(text);
        bytes += text.size();
        ++records;
        check();
    }
};
FatTreeStore::FatTreeStore(const std::string &path, const FatTreeExtractionRequest &r)
    : impl_(new Impl(path, r)) {
}
FatTreeStore::~FatTreeStore() = default;
V FatTreeStore::observation() const {
    impl_->check();
    return impl_->binding;
}
void FatTreeStore::check_unused() const {
    impl_->unused();
}
bool FatTreeStore::effects_possible() const {
    return impl_->effects;
}
bool FatTreeStore::reserved() const {
    return impl_->ready;
}
const std::string &FatTreeStore::operation_id() const {
    return impl_->operation;
}
std::size_t FatTreeStore::state_records() const {
    return impl_->records;
}
void FatTreeStore::reserve(const FatTreeReview &review, const FatTreeReviewGrant &grant,
                           const std::string &operation, const V &owner,
                           const std::string &process_digest) {
    auto &p = *impl_;
    validate_fat_tree_review_grant(review, grant);
    if (encode(field(review.definition, "operation_store")) != encode(observation()))
        fail("fat_tree_store_review_changed");
    if (p.effects || p.ready || operation.size() != 40 || operation.compare(0, 8, "tree-op:") ||
        operation.find_first_not_of("0123456789abcdef", 8) != operation.npos)
        fail("fat_tree_store_reservation");
    if (p.writer.kind == V::Kind::null)
        fail("fat_tree_store_writer_missing");
    p.unused();
    p.operation = operation;
    p.review_digest = review.digest;
    p.child_ids = V::array();
    for (std::size_t i = 0; i < 3; ++i) {
        bool created = false;
        try {
            p.files[i] =
                p.directory.open(names[i], GENERIC_READ | GENERIC_WRITE,
                                 i == 1 ? FILE_SHARE_READ | FILE_SHARE_WRITE : FILE_SHARE_READ,
                                 CREATE_NEW, &p.security.attributes, &created);
        } catch (...) {
            if (created)
                p.effects = true;
            throw;
        }
        if (created)
            p.effects = true;
        if (!p.files[i].valid())
            fail("fat_tree_store_create", GetLastError());
        p.child_ids.items.push_back(f::generation(p.files[i].value, false));
        p.check();
    }
    const auto controller = V::object()
                                .put("pid", number(GetCurrentProcessId()))
                                .put("created", V::string(w::process_created(GetCurrentProcess())));
    const auto header =
        V::object()
            .put("schema", V::string("org.disked.fat-tree-operation-request-prototype/2"))
            .put("operation_id", V::string(operation))
            .put("review", review.definition)
            .put("review_digest", V::string(review.digest))
            .put("process_owner", owner)
            .put("process_definition_digest", V::string(process_digest))
            .put("files", p.child_ids)
            .put("controller_host", V::string(p.security.host_id))
            .put("controller", controller)
            .put("writer", p.writer);
    const auto raw = encode(header);
    try {
        w::write_file(p.files[0].value, raw, "fat_tree_request");
        w::write_file(p.files[1].value, "0", "fat_tree_cancel");
    } catch (...) {
        p.uncertain = true;
        throw;
    }
    p.bytes = raw.size() + 1;
    p.ready = true;
    p.check();
}
void FatTreeStore::append_state(const char *phase, const V &worker) {
    impl_->append(phase, worker);
}
void FatTreeStore::request_cancel() {
    auto &p = *impl_;
    if (!p.ready)
        fail("fat_tree_store_not_reserved");
    p.check();
    const auto current = w::read_file(p.files[1].value, 1);
    if (current != "0" && current != "1")
        fail("fat_tree_store_cancel_changed");
    LARGE_INTEGER zero{};
    if (!SetFilePointerEx(p.files[1].value, zero, nullptr, FILE_BEGIN))
        fail("fat_tree_store_seek", GetLastError());
    try {
        w::write_file(p.files[1].value, "1", "fat_tree_cancel");
    } catch (...) {
        p.uncertain = true;
        throw;
    }
    p.check();
}
void FatTreeStore::bind_writer(const V &v) {
    if (impl_->effects || impl_->writer.kind != V::Kind::null)
        fail("fat_tree_store_writer_binding");
    const auto *pid = v.find("pid"), *created = v.find("created");
    if (!pid || !created || pid->kind != V::Kind::string || created->kind != V::Kind::string ||
        !json::decimal_u64(pid->text) || !json::decimal_u64(created->text) ||
        !std::stoull(pid->text) || std::stoull(pid->text) > UINT32_MAX ||
        !std::stoull(created->text))
        fail("fat_tree_store_writer_binding");
    impl_->writer = V::object().put("pid", *pid).put("created", *created);
}
bool FatTreeStore::cancellation_requested() const {
    const auto &p = *impl_;
    if (!p.ready)
        return false;
    p.check();
    const auto value = w::read_file(p.files[1].value, 1);
    if (value != "0" && value != "1")
        fail("fat_tree_store_cancel_changed");
    p.check();
    return value == "1";
}
} // namespace nt_inventory
} // namespace disked
