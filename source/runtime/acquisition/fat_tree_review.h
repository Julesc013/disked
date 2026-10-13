#pragma once
#include "runtime/command/json.h"

namespace disked {
struct FatTreeReviewError : std::runtime_error {
    explicit FatTreeReviewError(const char *code) : std::runtime_error(code) {
    }
};
struct FatTreeReview {
    const json::Value definition;
    const std::string digest;
};
struct FatTreeReviewGrant {
    std::string review_digest;
    bool source_read = false, destination_write = false, ledger_write = false;
    bool operation_write = false, host_effects = false;
};
// Pure private review model. Supplied observations authenticate no resource,
// actor or execution authority. Native admission must supply fresh owned facts.
FatTreeReview prepare_fat_tree_review(const json::Value &process_definition,
                                      const json::Value &operation_store);
FatTreeReview validate_fat_tree_review(const json::Value &definition);
void validate_fat_tree_review_grant(const FatTreeReview &, const FatTreeReviewGrant &);
bool same_fat_tree_review(const FatTreeReview &, const json::Value &fresh_process_definition,
                          const json::Value &fresh_operation_store);
json::Limits fat_tree_review_limits();
} // namespace disked
