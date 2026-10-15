#pragma once
#include "ntfs_capture.h"
#include "runtime/command/protocol.h"
#include <functional>

namespace disked {
struct NtfsInspectionRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0;
    NtfsFileProfile profile = NtfsFileProfile::Automatic;
};
struct NtfsInspectionRead {
    enum class Status { Captured, Refused, Unresolved };
    Status status = Status::Unresolved;
    json::Value file, context, worker;
    std::string diagnostic;
    std::uint32_t platform_code = 0;
};
using NtfsInspectionPort = std::function<NtfsInspectionRead(const NtfsInspectionRequest &)>;
bool ntfs_inspection_parameters(const json::Value &);
bool decode_ntfs_inspection(const json::Value &, NtfsInspectionRequest &);
json::Value project_ntfs_inspection(const NtfsInspectionRead &, const NtfsInspectionRequest &);
Outcome dispatch_ntfs_inspection(const std::string &, const json::Value &,
                                 const NtfsInspectionPort &);
constexpr std::size_t ntfs_inspection_response_bytes = 524288;
} // namespace disked
