#pragma once
#include "region_reader.h"
#include "runtime/command/json.h"
#include <cstddef>
#include <cstdint>
#include <string>

namespace disked {
enum class NtfsFileProfile { Automatic, Version30, Version31 };
enum class NtfsSnapshotKind {
    Bootstrap = 0,
    Directory = 1,
    Membership = 2,
    Upcase = 3,
    NameOrder = 4
};
struct NtfsCaptureLimits {
    std::size_t read_requests = 128, read_bytes = 1048576, retained_bytes = 262144;
    std::size_t attributes = 256, runs = 512, output_bytes = 1048576;
};
struct NtfsCaptureRequest {
    std::string source_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    unsigned major = 3, minor = 1;
    NtfsCaptureLimits limits;
};
// Private supplied-region facts only. Identity/version inputs are context;
// equal region rereads are neither a snapshot nor a current-source/effect grant.
void validate_ntfs_capture_request(const NtfsCaptureRequest &);
json::Value observe_ntfs_bootstrap(const NtfsCaptureRequest &, const RegionReader &);
json::Value observe_ntfs_upcase(const NtfsCaptureRequest &, const RegionReader &);
} // namespace disked
