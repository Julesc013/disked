#pragma once
#include "ntfs_directory.h"
#include <cstddef>

namespace disked {
struct NtfsMembershipRequest {
    NtfsDirectoryRequest directory;
    std::size_t targets = 64;
};
void validate_ntfs_membership_request(const NtfsMembershipRequest &);
// Private supplied-reader correspondence; neither lookup nor source authority.
json::Value observe_ntfs_membership(const NtfsMembershipRequest &, const RegionReader &);
} // namespace disked
