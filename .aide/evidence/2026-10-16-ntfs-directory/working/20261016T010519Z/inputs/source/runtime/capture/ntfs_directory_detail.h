#pragma once
#include "ntfs_directory.h"
#include <functional>
#include <memory>
#include <vector>

namespace disked {
struct NtfsJoinedStream;
namespace ntfs_directory_detail {
struct Geometry {
    std::uint64_t reference;
    std::uint32_t cluster_bytes, index_bytes;
    unsigned major, minor;
};
// Internal collaboration with the source-owning capture Observer. Callbacks
// resolve exact $I30 streams, read only validated mappings and charge its budget.
struct Port {
    std::function<std::unique_ptr<const NtfsJoinedStream>(unsigned)> stream;
    std::function<std::vector<unsigned char>(const NtfsJoinedStream &, std::uint64_t, std::size_t)>
        read;
    std::function<void(std::size_t)> charge;
};
// Output owns completed prefixes even if a source callback throws. The caller
// retains that source diagnostic; index_complete remains false on interruption.
void collect(NtfsDirectoryLimits, Geometry, Port, json::Value &);
} // namespace ntfs_directory_detail
} // namespace disked
