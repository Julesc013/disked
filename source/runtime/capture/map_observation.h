#pragma once
#include "json.h"
#include "checked.h"
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
}
