#pragma once
#include "region_reader.h"
#include "runtime/command/json.h"
#include <cstdint>
#include <string>

namespace disked {
struct FatCaptureLimits {
    std::size_t nodes = 128, depth = 8, chain_clusters = 1024, total_clusters = 4096;
    std::size_t records = 4096, read_requests = 8192, read_bytes = 2097152;
    std::size_t orphan_groups = 128, output_bytes = 1048576, compare_copies = 16;
};
struct FatCaptureRequest {
    std::string source_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0;
    FatCaptureLimits limits;
};
// Private supplied-reader observation. Limits/geometry are checked; returned
// JSON owns all metadata. No source identity/freshness, extraction or writer grant.
json::Value observe_fat_volume(const FatCaptureRequest &, const RegionReader &);
} // namespace disked
