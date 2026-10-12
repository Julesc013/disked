#pragma once
#include "runtime/capture/fat_capture.h"
#include <functional>

namespace disked {
struct FatFileRegion {
    std::uint64_t offset = 0;
    std::size_t requested = 0;
    std::uint32_t error = 0;
    std::vector<unsigned char> bytes;
};
struct FatFileRead {
    json::Value result;
    std::vector<FatFileRegion> regions;
    std::uint64_t process_id = 0, process_created = 0;
};
FatFileRead capture_fat_file_owned(const std::string &path, std::uint64_t volume_offset,
                                   std::uint64_t volume_bytes, std::uint32_t fat_copy,
                                   const FatCaptureLimits &limits, bool allocation_scan,
                                   bool auxiliary_checks, const FatNameConsumer *namespace_consumer,
                                   const std::vector<FatNameQuery> &namespace_queries,
                                   const FatNamespaceLimits &namespace_limits,
                                   const json::Value *expected_source = nullptr,
                                   const std::function<bool()> &stop = {});
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
