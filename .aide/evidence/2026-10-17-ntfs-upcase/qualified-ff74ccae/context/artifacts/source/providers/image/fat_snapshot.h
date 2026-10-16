#pragma once
#include "fat_file.h"
#include "fat_content_file.h"
#include <memory>

namespace disked {
namespace nt_inventory {
class FatWorker;
}
struct FatSnapshotInput {
    std::uint64_t capture_epoch = 0, volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0, name_code_page = 0;
    std::string path;
    json::Value expected_source;
    bool allocation_scan = false, auxiliary_checks = false;
    FatAllocationWindow allocation_window;
    FatCaptureLimits limits;
    std::vector<FatNameQuery> queries;
    FatNamespaceLimits namespace_limits;
    bool content_enabled = false;
    FatFileContentRequest content;
    json::Value fixture = json::Value::object();
};
constexpr std::size_t fat_snapshot_payload_bytes = 8U * 1024U * 1024U;
json::Limits fat_snapshot_json_limits(bool content_enabled = false);
void validate_fat_snapshot_input(const FatSnapshotInput &);
json::Value fat_snapshot_input_value(const FatSnapshotInput &);
FatSnapshotInput fat_snapshot_input_from(const json::Value &);
// An ephemeral transport frame. Its verification authenticates no process by itself.
json::Value read_fat_snapshot_frame(const FatSnapshotInput &,
                                    const std::function<bool()> &stop = {});
json::Value verify_fat_snapshot_frame(const json::Value &, const FatSnapshotInput &);
json::Value fat_snapshot_claims();
class FatFileSnapshot final {
    const json::Value result_, context_, frame_;
    FatFileSnapshot(json::Value result, json::Value context, json::Value frame)
        : result_(std::move(result)), context_(std::move(context)), frame_(std::move(frame)) {
    }
    friend class nt_inventory::FatWorker;

  public:
    const json::Value &result() const {
        return result_;
    }
    const json::Value &context() const {
        return context_;
    }
    const json::Value &frame() const {
        return frame_;
    }
};
} // namespace disked
