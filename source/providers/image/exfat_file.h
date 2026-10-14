#pragma once
#include "runtime/capture/exfat_capture.h"
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
                                       const std::function<bool()> &stop = {});
#ifdef DISKED_EXFAT_FILE_TESTING
// Compiled only into the separate fixture library/probe. No environment protocol.
struct ExfatFileTestControl {
    std::function<void(std::size_t, ExfatFileRegion &)> after_read;
    std::function<void(json::Value &)> after_metadata;
    std::function<void(std::size_t, ExfatFileRegion &)> before_replay;
    std::function<void(std::size_t)> before_binding;
};
ExfatFileRead capture_exfat_file_testing(const std::string &, std::uint64_t, std::uint64_t, bool,
                                         const ExfatCaptureLimits &, const std::function<bool()> &,
                                         const ExfatFileTestControl &);
#endif
} // namespace disked
