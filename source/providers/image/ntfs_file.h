#pragma once
#include "runtime/capture/ntfs_directory.h"
#include <cstddef>
#include <functional>
#include <vector>

namespace disked {
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
struct NtfsDirectoryFileRequest {
    NtfsFileRequest file;
    std::uint64_t reference = 0;
    NtfsDirectoryLimits limits;
};
struct NtfsMembershipFileRequest {
    NtfsDirectoryFileRequest directory;
    std::size_t targets = 64;
};
// Private synchronous ordinary-file observation. Native waits need containment
// before frontend admission; no physical opening or future source/effect grant.
NtfsFileRead capture_ntfs_file_owned(const NtfsFileRequest &,
                                     const std::function<bool()> &stop = {});
NtfsFileRead capture_ntfs_upcase_file_owned(const NtfsFileRequest &,
                                            const std::function<bool()> &stop = {});
NtfsFileRead capture_ntfs_directory_file_owned(const NtfsDirectoryFileRequest &,
                                               const std::function<bool()> &stop = {});
NtfsFileRead capture_ntfs_name_order_file_owned(const NtfsDirectoryFileRequest &,
                                                const std::function<bool()> &stop = {});
NtfsFileRead capture_ntfs_membership_file_owned(const NtfsMembershipFileRequest &,
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
NtfsFileRead capture_ntfs_upcase_file_testing(const NtfsFileRequest &,
                                              const std::function<bool()> &,
                                              const NtfsFileTestControl &);
NtfsFileRead capture_ntfs_directory_file_testing(const NtfsDirectoryFileRequest &,
                                                 const std::function<bool()> &,
                                                 const NtfsFileTestControl &);
NtfsFileRead capture_ntfs_name_order_file_testing(const NtfsDirectoryFileRequest &,
                                                  const std::function<bool()> &,
                                                  const NtfsFileTestControl &);
NtfsFileRead capture_ntfs_membership_file_testing(const NtfsMembershipFileRequest &,
                                                  const std::function<bool()> &,
                                                  const NtfsFileTestControl &);
#endif
} // namespace disked
