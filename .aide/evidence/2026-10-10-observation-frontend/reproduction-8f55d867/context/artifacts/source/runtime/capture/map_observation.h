#pragma once
#include "json.h"
#include "checked.h"
#include "extent.h"
#include "view.h"
#include <functional>
#include <vector>

namespace disked {
struct MapObservationError : std::runtime_error {
    explicit MapObservationError(const char* code):std::runtime_error(code) {}
};
// Private bounded interpretation of an immutable captured prefix. The caller
// keeps bytes immutable for this call. No I/O or source-consistency assertion.
// Returned values own their data and retain no reader/workspace borrows.
json::Value observe_partition_map(const std::vector<unsigned char>& bytes,
    const de_u64& blocks,de_u32 logical_block_bytes);
// Private metadata-region source. Views must remain alive and immutable until
// this call returns. The callback receives a checked half-open byte extent;
// missing bytes are a short/empty view. No callback or view escapes in the result.
using MapRegionReader=std::function<de_view(const de_byte_extent&)>;
json::Value observe_partition_regions(const de_u64& blocks,
    de_u32 logical_block_bytes,const MapRegionReader& reader);
}
