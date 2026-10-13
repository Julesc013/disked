#pragma once
#include "runtime/capture/fat_traversal.h"

namespace disked {
namespace nt_inventory {
class FatTreeWorker;
}
struct FatTreeInput {
    std::string path;
    json::Value expected_source;
    std::uint64_t capture_epoch = 0, volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0;
    FatTraversalResources resources;
    FatTraversalPageBudget page;
    json::Value fixture = json::Value::object();
};
constexpr std::size_t fat_tree_frame_bytes = 2U * 1024U * 1024U;
json::Limits fat_tree_json_limits();
void validate_fat_tree_input(const FatTreeInput &);
json::Value fat_tree_input_value(const FatTreeInput &);
FatTreeInput fat_tree_input_from(const json::Value &);
FatTraversalBinding fat_tree_binding(const FatTreeInput &, const json::Value &context);
json::Value fat_tree_binding_value(const FatTraversalBinding &);
json::Value fat_tree_claims();
// Stateful pure replay owns copied current-page bytes. Opens no source and
// authenticates no process; the actual worker checks its real launch context.
class FatTreeReplay {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    explicit FatTreeReplay(const FatTreeInput &);
    ~FatTreeReplay();
    FatTreeReplay(const FatTreeReplay &) = delete;
    FatTreeReplay &operator=(const FatTreeReplay &) = delete;
    json::Value accept(const json::Value &frame);
    bool finished() const;
};
class FatTreePage final {
    const json::Value frame_, context_;
    FatTreePage(json::Value frame, json::Value context)
        : frame_(std::move(frame)), context_(std::move(context)) {
    }
    friend class nt_inventory::FatTreeWorker;

  public:
    const json::Value &frame() const {
        return frame_;
    }
    const json::Value &context() const {
        return context_;
    }
};
} // namespace disked
