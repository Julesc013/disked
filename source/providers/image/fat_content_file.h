#pragma once
#include "runtime/capture/fat_content.h"

namespace disked {
struct FatFileContentRequest {
    std::uint64_t reference_capture_epoch = 0, node_id = 0, expected_file_bytes = 0, offset = 0;
    std::size_t count = 0;
    FatContentLimits limits;
    std::string metadata_digest;
};
void validate_fat_file_content_request(const FatFileContentRequest &);
json::Value fat_file_content_request_value(const FatFileContentRequest &);
FatFileContentRequest fat_file_content_request_from(const json::Value &);
// Comparison digest of the exact metadata observation with only its capture
// epoch replaced by zero. It authenticates no native source or process.
std::string fat_content_metadata_digest(const json::Value &);
} // namespace disked
