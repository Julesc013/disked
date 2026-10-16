#pragma once
#include "providers/image/exfat_file.h"
#include <memory>
#include <utility>

namespace disked {
namespace nt_inventory {
class ExfatWorker;
}
struct ExfatSnapshotInput {
    std::uint64_t capture_epoch = 0, volume_offset = 0, volume_bytes = 0;
    std::string path;
    json::Value expected_source;
    ExfatUpcaseFormat upcase_format = ExfatUpcaseFormat::Automatic;
    ExfatCaptureLimits limits;
    json::Value fixture = json::Value::object();
};
constexpr std::size_t exfat_snapshot_payload_bytes = 8U * 1024U * 1024U;
json::Limits exfat_snapshot_json_limits();
void validate_exfat_snapshot_input(const ExfatSnapshotInput &);
json::Value exfat_snapshot_input_value(const ExfatSnapshotInput &);
ExfatSnapshotInput exfat_snapshot_input_from(const json::Value &);
json::Value read_exfat_snapshot_frame(const ExfatSnapshotInput &,
                                      const std::function<bool()> &stop = {});
json::Value verify_exfat_snapshot_frame(const json::Value &, const ExfatSnapshotInput &);
json::Value exfat_snapshot_claims();
class ExfatFileSnapshot final {
    const json::Value result_, context_, frame_;
    ExfatFileSnapshot(json::Value result, json::Value context, json::Value frame)
        : result_(std::move(result)), context_(std::move(context)), frame_(std::move(frame)) {
    }
    friend class nt_inventory::ExfatWorker;

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
