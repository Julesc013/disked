#pragma once
#include "runtime/capture/exfat_capture.h"
#include "runtime/capture/exfat_tree.h"
#include <functional>
#include <string>
#include <vector>

namespace disked {
struct ExfatFileRegion {
    std::uint64_t offset = 0;
    std::size_t requested = 0;
    std::uint32_t error = 0;
    bool read_attempted = false;
    std::string refusal;
    std::vector<unsigned char> bytes;
};
struct ExfatFileRead {
    json::Value result;
    std::vector<ExfatFileRegion> regions;
    std::uint64_t process_id = 0, process_created = 0;
};
// Private synchronous read-only ordinary-file adapter. Requires containment
// before frontend admission; no physical source opening or current-source grant.
ExfatFileRead capture_exfat_file_owned(const std::string &path, std::uint64_t offset,
                                       std::uint64_t bytes, bool compressed,
                                       const ExfatCaptureLimits &limits = {},
                                       const std::function<bool()> &stop = {},
                                       const json::Value *expected_source = nullptr);
// Private tree observation only. No worker/public transport or effect authority.
ExfatFileRead capture_exfat_tree_file_owned(const std::string &path, std::uint64_t offset,
                                            std::uint64_t bytes, ExfatUpcaseFormat format,
                                            const ExfatTreeLimits &tree_limits = {},
                                            const ExfatCaptureLimits &root_limits = {},
                                            const std::function<bool()> &stop = {},
                                            const json::Value *expected_source = nullptr);
// Typed private v2 encoding; explicit boolean overload above retains v1.
ExfatFileRead capture_exfat_file_owned(const std::string &path, std::uint64_t offset,
                                       std::uint64_t bytes, ExfatUpcaseFormat format,
                                       const ExfatCaptureLimits &limits = {},
                                       const std::function<bool()> &stop = {},
                                       const json::Value *expected_source = nullptr);
#ifdef DISKED_EXFAT_FILE_TESTING
// Compiled only into the separate fixture library/probe. No environment protocol.
struct ExfatFileTestControl {
    std::function<void(std::size_t, ExfatFileRegion &)> after_read;
    std::function<void(json::Value &)> after_metadata;
    std::function<void(std::size_t, ExfatFileRegion &)> before_replay;
    std::function<void(std::size_t)> before_binding;
    std::function<void(std::size_t, bool &)> before_applicability_replay;
};
ExfatFileRead capture_exfat_file_testing(const std::string &, std::uint64_t, std::uint64_t, bool,
                                         const ExfatCaptureLimits &, const std::function<bool()> &,
                                         const ExfatFileTestControl &,
                                         const json::Value *expected_source = nullptr);
ExfatFileRead capture_exfat_file_testing(const std::string &, std::uint64_t, std::uint64_t,
                                         ExfatUpcaseFormat, const ExfatCaptureLimits &,
                                         const std::function<bool()> &,
                                         const ExfatFileTestControl &,
                                         const json::Value *expected_source = nullptr);
ExfatFileRead capture_exfat_tree_file_testing(const std::string &, std::uint64_t, std::uint64_t,
                                              ExfatUpcaseFormat, const ExfatTreeLimits &,
                                              const ExfatCaptureLimits &,
                                              const std::function<bool()> &,
                                              const ExfatFileTestControl &,
                                              const json::Value *expected_source = nullptr);
#endif
} // namespace disked
