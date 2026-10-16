#pragma once
#include "providers/image/ntfs_file.h"
#include <cstddef>
#include <memory>
#include <utility>

namespace disked {
namespace nt_inventory {
class NtfsWorker;
}
struct NtfsSnapshotInput {
    std::uint64_t capture_epoch = 0, volume_offset = 0, volume_bytes = 0;
    std::string path;
    json::Value expected_source;
    NtfsFileProfile profile = NtfsFileProfile::Automatic;
    NtfsCaptureLimits limits;
    json::Value fixture = json::Value::object();
    NtfsSnapshotKind kind = NtfsSnapshotKind::Bootstrap;
    std::uint64_t directory_reference = 0;
    NtfsDirectoryLimits directory_limits;
    std::size_t target_limit = 64;
};
constexpr std::size_t ntfs_snapshot_payload_bytes = 8U * 1024U * 1024U;
json::Limits ntfs_snapshot_json_limits();
void validate_ntfs_snapshot_input(const NtfsSnapshotInput &);
json::Value ntfs_snapshot_input_value(const NtfsSnapshotInput &);
NtfsSnapshotInput ntfs_snapshot_input_from(const json::Value &);
json::Value read_ntfs_snapshot_frame(const NtfsSnapshotInput &,
                                     const std::function<bool()> &stop = {});
json::Value verify_ntfs_snapshot_frame(const json::Value &, const NtfsSnapshotInput &);
json::Value ntfs_snapshot_claims();
class NtfsFileSnapshot final {
    const json::Value result_, context_, frame_;
    NtfsFileSnapshot(json::Value result, json::Value context, json::Value frame)
        : result_(std::move(result)), context_(std::move(context)), frame_(std::move(frame)) {
    }
    friend class nt_inventory::NtfsWorker;

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
