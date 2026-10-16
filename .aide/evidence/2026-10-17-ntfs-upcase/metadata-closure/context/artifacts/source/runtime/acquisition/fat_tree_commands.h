#pragma once
#include "fat_tree_review.h"
#include "runtime/command/protocol.h"
#include <functional>

namespace disked {
struct FatTreeCommandActions {
    std::function<json::Value(const json::Value &)> prepare;
    std::function<json::Value(const FatTreeReview &, const FatTreeReviewGrant &)> execute;
};
// Shared command semantics over inward-facing ports. Schema/semantic/grant
// checks precede invocation; no platform/provider or separate frontend parser.
Outcome dispatch_fat_tree_extraction(const Registry &, const std::string &request,
                                     const json::Value &, const FatTreeCommandActions &);
Outcome fat_tree_command_unresolved(const std::string &request, const json::Value &parameters);
} // namespace disked
