#pragma once
#include "ntfs_directory.h"
#include "runtime/command/protocol.h"
#include <cstddef>
#include <functional>

namespace disked {
struct NtfsInspectionRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0;
    NtfsFileProfile profile = NtfsFileProfile::Automatic;
    NtfsSnapshotKind kind = NtfsSnapshotKind::Bootstrap;
    std::uint64_t directory_reference = 0;
    std::size_t target_limit = 64;
};
struct NtfsInspectionRead {
    enum class Status { Captured, Refused, Unresolved };
    Status status = Status::Unresolved;
    json::Value file, context, worker;
    std::string diagnostic;
    std::uint32_t platform_code = 0;
};
using NtfsInspectionPort = std::function<NtfsInspectionRead(const NtfsInspectionRequest &)>;
void validate_ntfs_inspection_request(const NtfsInspectionRequest &);
NtfsCaptureLimits ntfs_inspection_capture_limits(NtfsSnapshotKind);
NtfsDirectoryLimits ntfs_inspection_directory_limits();
bool ntfs_inspection_parameters(const json::Value &);
bool decode_ntfs_inspection(const json::Value &, NtfsInspectionRequest &);
json::Value project_ntfs_inspection(const NtfsInspectionRead &, const NtfsInspectionRequest &);
Outcome dispatch_ntfs_inspection(const std::string &, const json::Value &,
                                 const NtfsInspectionPort &);
constexpr std::size_t ntfs_inspection_response_bytes = 524288;
} // namespace disked
