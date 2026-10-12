#pragma once
#include "runtime/capture/fat_capture.h"

namespace disked {
// Private Windows ordinary-image adapter. Read-only; synchronous waits require
// external containment before frontend admission. Does not mount or extract files.
json::Value capture_fat_file(const std::string &path, std::uint64_t volume_offset,
                             std::uint64_t volume_bytes, std::uint32_t fat_copy,
                             const FatCaptureLimits &limits = FatCaptureLimits{},
                             bool allocation_scan = false, bool auxiliary_checks = false,
                             const FatNameConsumer *namespace_consumer = nullptr,
                             const std::vector<FatNameQuery> &namespace_queries = {},
                             const FatNamespaceLimits &namespace_limits = FatNamespaceLimits{});
} // namespace disked
