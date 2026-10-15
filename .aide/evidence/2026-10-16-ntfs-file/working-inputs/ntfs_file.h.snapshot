#pragma once
#include "runtime/capture/ntfs_capture.h"
#include <functional>
#include <vector>

namespace disked {
enum class NtfsFileProfile { Automatic, Version30, Version31 };
struct NtfsFileRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0;
    NtfsFileProfile profile = NtfsFileProfile::Automatic;
    NtfsCaptureLimits limits;
    json::Value expected_source;
};
struct NtfsFileRegion {
    std::uint64_t offset = 0;
    std::size_t requested = 0;
    std::uint32_t error = 0;
    bool seek_attempted = false, read_attempted = false;
    std::string refusal;
    std::vector<unsigned char> bytes;
};
struct NtfsFileRead {
    json::Value result;
    std::vector<NtfsFileRegion> regions;
};
// Private synchronous ordinary-file observation. Native waits need containment
// before frontend admission; no physical opening or future source/effect grant.
NtfsFileRead capture_ntfs_file_owned(const NtfsFileRequest &,
                                     const std::function<bool()> &stop = {});
#ifdef DISKED_NTFS_FILE_TESTING
struct NtfsFileTestControl {
    std::function<void(std::size_t)> before_binding;
    std::function<void(std::size_t, NtfsFileRegion &)> after_read;
    std::function<void(json::Value &)> after_metadata;
    std::function<void(std::size_t, NtfsFileRegion &)> before_replay;
};
NtfsFileRead capture_ntfs_file_testing(const NtfsFileRequest &, const std::function<bool()> &,
                                       const NtfsFileTestControl &);
#endif
} // namespace disked
