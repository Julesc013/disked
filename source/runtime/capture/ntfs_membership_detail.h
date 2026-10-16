#pragma once
#include "ntfs_directory_detail.h"
#include "ntfs_names.h"
#include <functional>

namespace disked {
namespace ntfs_membership_detail {
struct Port {
    // Source-owned acquisition fills a bounded owned prefix even if it throws.
    std::function<NtfsFilenamesResult(std::uint64_t, json::Value &)> target;
    std::function<void(std::size_t)> charge;
};
// Local comparison failures are reported here; the caller retains source errors.
void collect(const std::vector<ntfs_directory_detail::Edge> &, std::size_t targets, Port,
             json::Value &);
} // namespace ntfs_membership_detail
} // namespace disked
