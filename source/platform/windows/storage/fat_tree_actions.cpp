#include "fat_tree_actions.h"
#include "fat_tree_admission.h"
#include "fat_tree_controller.h"

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw FatTreeStoreError("fat_tree_action_shape");
    return *p;
}
std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw FatTreeStoreError("fat_tree_action_shape");
    return p->text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw FatTreeStoreError("fat_tree_action_integer");
    return std::stoull(s);
}
V prepare(const V &p) {
    FatTreeExtractionRequest r;
    r.tree.path = text(p, "source");
    r.tree.volume_offset = integer(p, "volume_offset");
    r.tree.volume_bytes = integer(p, "volume_bytes");
    r.tree.fat_copy = static_cast<std::uint32_t>(integer(p, "fat_copy"));
    r.tree.capture_epoch = integer(p, "capture_epoch");
    r.destination = text(p, "destination");
    r.ledger = text(p, "ledger");
    r.metadata.oem_code_page = static_cast<std::uint32_t>(integer(p, "oem_code_page"));
    r.metadata.name_selection = text(p, "name_selection", "long_or_short");
    r.metadata.unrepresentable_name = text(p, "unrepresentable_name", "refuse");
    r.metadata.time_interpretation = text(p, "time_interpretation", "preserve_raw");
    r.metadata.utc_offset_minutes = std::stoi(text(p, "utc_offset_minutes", "0"));
    auto owner = FatTreeAdmission::prepare(r, text(p, "state_directory"));
    owner->launch();
    const auto start = GetTickCount64();
    V last;
    while (!owner->prepared_review()) {
        last = owner->observe();
        if (field(last, "admission_failed").boolean)
            throw FatTreeStoreError(text(last, "diagnostic").c_str());
        if (text(field(field(last, "worker"), "worker"), "observation") == "exited" ||
            GetTickCount64() - start >= 10000) {
            owner->cancel();
            owner->retire();
            throw FatTreeStoreError("fat_tree_preparation_unavailable");
        }
        Sleep(10);
    }
    const auto review = owner->prepared_review();
    owner->cancel();
    last = owner->retire();
    if (text(field(field(last, "worker"), "worker"), "observation") != "exited")
        throw FatTreeStoreError("fat_tree_preparation_exit_unresolved");
    return V::object()
        .put("definition", review->definition)
        .put("definition_digest", V::string(review->digest))
        .put("preparation", last);
}
V execute(const FatTreeReview &r, const FatTreeReviewGrant &g) {
    auto controller = FatTreeController::prepare(r, g);
    controller->launch();
    controller->dispatch();
    const auto start = GetTickCount64();
    V last;
    do {
        last = controller->observe();
        if (text(last, "status") != "dispatch_pending")
            return last;
        Sleep(10);
    } while (GetTickCount64() - start < 1000);
    // A timed-out caller retains the preallocated identity and exact store. It
    // can inspect later; it does not assume effects failed or dispatch again.
    last.put("status", V::string("unknown"))
        .put("diagnostic", V::string("fat_tree_admission_pending"));
    return last;
}
} // namespace
FatTreeCommandActions fat_tree_command_actions() {
    return {prepare, execute};
}
} // namespace nt_inventory
} // namespace disked
