#include "fat_tree_admission.h"
#include "platform/windows/worker_files.h"
#include <algorithm>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
const V &field(const V &v, const char *name) {
    const auto *p = v.find(name);
    if (!p)
        throw FatTreeStoreError("fat_tree_admission_shape");
    return *p;
}
std::string text(const V &v, const char *name) {
    const auto &p = field(v, name);
    if (p.kind != V::Kind::string)
        throw FatTreeStoreError("fat_tree_admission_shape");
    return p.text;
}
std::uint64_t number(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw FatTreeStoreError("fat_tree_admission_integer");
    return std::stoull(s);
}
FatTreeExtractionRequest request_from_review(const FatTreeReview &review) {
    const auto &b = field(review.definition, "backend");
    auto input = field(b, "prepared_input");
    input.put("fixture", V::object());
    FatTreeExtractionRequest request;
    request.tree = fat_tree_input_from(input);
    request.destination = text(field(b, "paths"), "destination");
    request.ledger = text(field(b, "paths"), "ledger");
    const auto &p = field(b, "metadata_policy"), &limits = field(b, "budgets");
    request.metadata.name_selection = text(p, "name_selection");
    request.metadata.unrepresentable_name = text(p, "unrepresentable_name");
    request.metadata.oem_code_page = static_cast<std::uint32_t>(number(p, "oem_code_page"));
    request.metadata.time_interpretation = text(p, "time_interpretation");
    request.metadata.utc_offset_minutes = std::stoi(text(p, "utc_offset_minutes"));
    request.entries = static_cast<std::size_t>(number(limits, "entries"));
    request.directories = static_cast<std::size_t>(number(limits, "directories"));
    request.metadata_bytes = static_cast<std::size_t>(number(limits, "metadata_bytes"));
    request.pages = static_cast<std::size_t>(number(limits, "pages"));
    request.content_bytes = number(limits, "content_bytes");
    request.ledger_bytes = number(limits, "ledger_bytes");
    return request;
}
bool exited(const V &v) {
    return text(field(v, "worker"), "observation") == "exited";
}
FatTreeExtractionRequest native_request(const FatTreeExtractionRequest &r) {
    auto request = r;
    if (request.tree.expected_source.kind == V::Kind::null) {
        const auto path = local_file::path_for(request.tree.path);
        auto parents = local_file::pin_parents(path);
        local_file::Handle source(
            CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, nullptr));
        if (source.value == INVALID_HANDLE_VALUE)
            throw FatTreeStoreError("fat_tree_admission_source", GetLastError());
        local_file::ordinary(source.value, false);
        local_file::bind_path(source.value, path);
        request.tree.expected_source = local_file::metadata(source.value).value;
        request.tree.path = local_file::utf8(path);
        // The existing worker factory independently rechecks this generation
        // while acquiring its own held source/ancestor closure.
    }
    return request;
}
} // namespace
struct FatTreeAdmission::Impl {
    std::shared_ptr<FatTreeStore> store;
    std::unique_ptr<FatTreeExtractionWorker> worker;
    std::shared_ptr<const FatTreeReview> review;
    std::string operation, diagnostic;
    bool failed = false, dispatched = false, publication_recorded = false, exit_recorded = false;
    std::uint64_t next_progress = 1;
    Impl(const FatTreeExtractionRequest &r, const std::string &path, const V &fixture)
        : store(std::make_shared<FatTreeStore>(path, r)),
          worker(FatTreeExtractionWorker::prepare(native_request(r), fixture)) {
        worker->retain_store(store);
    }
    void persist(const V &state) {
        if (!store->reserved())
            return;
        if (exit_recorded)
            return;
        if (field(state, "outcome").kind != V::Kind::null && !publication_recorded) {
            store->append_state("outcome_published", state);
            publication_recorded = true;
        }
        if (exited(state)) {
            store->append_state("exited", state);
            exit_recorded = true;
            return;
        }
        const auto pulse = number(state, "progress_pulse");
        // Progress is observational and may coalesce. Preserve terminal slots.
        if (dispatched && !publication_recorded && pulse >= next_progress &&
            store->state_records() < 60) {
            store->append_state("observing", state);
            next_progress =
                pulse > UINT64_MAX / 2 ? UINT64_MAX : std::max<std::uint64_t>(2, pulse * 2);
        }
    }
};
FatTreeAdmission::FatTreeAdmission(std::unique_ptr<Impl> p) : impl_(std::move(p)) {
}
FatTreeAdmission::~FatTreeAdmission() = default;
std::unique_ptr<FatTreeAdmission> FatTreeAdmission::prepare(const FatTreeExtractionRequest &r,
                                                            const std::string &path,
                                                            const V &fixture) {
    return std::unique_ptr<FatTreeAdmission>(
        new FatTreeAdmission(std::unique_ptr<Impl>(new Impl(r, path, fixture))));
}
std::unique_ptr<FatTreeAdmission> FatTreeAdmission::for_execution(const FatTreeReview &review,
                                                                  const FatTreeReviewGrant &grant,
                                                                  const V &fixture) {
    validate_fat_tree_review_grant(review, grant);
    const auto r = request_from_review(review);
    const auto path = text(field(field(review.definition, "operation_store"), "observed"), "path");
    auto out = prepare(r, path, fixture);
    // Store generation mismatch is rejected before source-worker launch.
    if (json::dump(out->impl_->store->observation(), fat_tree_review_limits()) !=
        json::dump(field(review.definition, "operation_store"), fat_tree_review_limits()))
        throw FatTreeStoreError("fat_tree_admission_store_changed");
    return out;
}
void FatTreeAdmission::launch() {
    impl_->store->check_unused();
    impl_->worker->launch();
    impl_->worker->release();
}
std::shared_ptr<const FatTreeReview> FatTreeAdmission::prepared_review() const {
    return impl_->review;
}
V FatTreeAdmission::observe(DWORD wait_ms) {
    auto &p = *impl_;
    auto state = p.worker->observe(wait_ms);
    try {
        if (p.store->cancellation_requested()) {
            p.worker->cancel();
            state = p.worker->observe();
        }
        if (!p.store->effects_possible())
            p.store->check_unused();
        if (!p.review)
            if (const auto prepared = p.worker->prepared())
                p.review = std::make_shared<FatTreeReview>(
                    prepare_fat_tree_review(prepared->definition(), p.store->observation()));
        p.persist(state);
    } catch (const std::exception &e) {
        p.failed = true;
        p.diagnostic = e.what();
        p.worker->cancel();
        state.put("status", V::string("unknown"));
    }
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-admission-observation-prototype/1"))
        .put("operation_id", p.operation.empty() ? V{} : V::string(p.operation))
        .put("worker", state)
        .put("review_digest", p.review ? V::string(p.review->digest) : V{})
        .put("store_effects_possible", V::boolean_value(p.store->effects_possible()))
        .put("admission_failed", V::boolean_value(p.failed))
        .put("diagnostic", p.diagnostic.empty() ? V{} : V::string(p.diagnostic))
        .put("persistent_reconnect_qualified", V::boolean_value(false));
}
void FatTreeAdmission::grant(const FatTreeReview &review, const FatTreeReviewGrant &grant,
                             const std::string &reserved_operation) {
    validate_fat_tree_review_grant(review, grant);
    auto &p = *impl_;
    if (p.failed || p.dispatched)
        throw FatTreeStoreError("fat_tree_admission_unavailable");
    const auto state = p.worker->observe();
    const auto prepared = p.worker->prepared();
    if (!prepared || text(state, "status") != "awaiting_grant")
        throw FatTreeStoreError("fat_tree_admission_not_prepared");
    p.store->check_unused();
    if (!same_fat_tree_review(review, prepared->definition(), p.store->observation()))
        throw FatTreeStoreError("fat_tree_admission_review_changed");
    worker_files::Security security;
    if (!reserved_operation.empty() &&
        (reserved_operation.size() != 40 || reserved_operation.compare(0, 8, "tree-op:") ||
         reserved_operation.find_first_not_of("0123456789abcdef", 8) != reserved_operation.npos))
        throw FatTreeStoreError("fat_tree_admission_operation_identity");
    p.operation = reserved_operation.empty() ? security.identity("tree-op:") : reserved_operation;
    try {
        p.store->bind_writer(field(state, "worker"));
        p.store->reserve(review, grant, p.operation, prepared->owner(), prepared->digest());
        p.store->append_state("admitted", state);
        p.store->append_state("dispatch_possible", state);
        if (p.store->cancellation_requested()) {
            p.worker->cancel();
            throw FatTreeStoreError("fat_tree_admission_cancel_before_dispatch");
        }
        p.worker->grant({prepared->digest(), grant.source_read, grant.destination_write,
                         grant.ledger_write, grant.host_effects});
        p.dispatched = true;
    } catch (const std::exception &e) {
        p.failed = true;
        p.diagnostic = e.what();
        p.worker->cancel();
        try {
            if (p.store->reserved())
                p.store->append_state("admission_uncertain", p.worker->observe());
        } catch (...) {
        }
        throw;
    }
}
void FatTreeAdmission::cancel() {
    auto &p = *impl_;
    try {
        if (p.store->reserved())
            p.store->request_cancel();
    } catch (const std::exception &e) {
        p.failed = true;
        p.diagnostic = e.what();
        p.worker->cancel();
        throw;
    }
    p.worker->cancel();
}
V FatTreeAdmission::retire(DWORD wait_ms) {
    impl_->worker->retire(wait_ms);
    return observe();
}
} // namespace nt_inventory
} // namespace disked
