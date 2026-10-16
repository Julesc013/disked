#pragma once
#include "ntfs_capture.h"
#include <cstddef>

namespace disked {
struct NtfsDirectoryLimits {
    std::size_t entries = 4096, blocks = 64, bitmap_bytes = 65536;
};
struct NtfsDirectoryRequest {
    NtfsCaptureRequest capture;
    // Zero discovers reserved root FILE5; otherwise require the full reference.
    std::uint64_t reference = 0;
    NtfsDirectoryLimits limits;
};
void validate_ntfs_directory_request(const NtfsDirectoryRequest &);
// Private supplied-reader acquisition/framing, not namespace or effect authority.
json::Value observe_ntfs_directory(const NtfsDirectoryRequest &, const RegionReader &);
} // namespace disked
