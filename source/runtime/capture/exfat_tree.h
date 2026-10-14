#pragma once
#include "exfat_capture.h"
#include <functional>

namespace disked {
struct ExfatTreeLimits {
    std::size_t directories = 256, depth = 32, clusters = 4096, records = 4096;
    std::size_t read_requests = 16384, read_bytes = 8388608, retained_bytes = 8388608;
    std::size_t content_bytes = 1048576, output_bytes = 4194304;
};
struct ExfatTreePort {
    RegionReader read;
    // Exact provider observation, not authentication or snapshot authority.
    std::function<bool(const ExfatCaptureRequest &)> applicable;
};
// Bounded supplied-reader observations; no native opening or effect grant.
json::Value observe_exfat_tree(const ExfatCaptureRequest &, const ExfatTreePort &,
                               const ExfatTreeLimits & = ExfatTreeLimits{});
} // namespace disked
