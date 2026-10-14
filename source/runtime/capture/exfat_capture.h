#pragma once
#include "runtime/capture/region_reader.h"
#include "runtime/command/json.h"
#include <cstdint>
#include <string>

namespace disked {
enum class ExfatUpcaseFormat { Compressed, Literal, Automatic };
struct ExfatCaptureLimits {
    std::size_t read_requests = 8192, read_bytes = 2097152;
    std::size_t clusters = 4096, records = 4096, retained_bytes = 1048576;
    std::size_t output_bytes = 1048576;
};
struct ExfatCaptureRequest {
    std::string source_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    ExfatUpcaseFormat upcase_format = ExfatUpcaseFormat::Compressed;
    ExfatCaptureLimits limits;
};
// Supplied-reader observations only; no native opening or current-source grant.
void validate_exfat_capture_request(const ExfatCaptureRequest &);
json::Value observe_exfat_volume(const ExfatCaptureRequest &, const RegionReader &);
} // namespace disked
