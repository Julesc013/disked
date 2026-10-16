#pragma once
#include "ntfs_stream.h"

namespace disked {
// Supplied-record assertions only; source acquisition establishes provenance.
struct NtfsFilenameRequest {
    NtfsStreamContext context;
    std::uint64_t base_reference = 0, volume_clusters = 0;
    std::uint32_t cluster_bytes = 4096, record_bytes = 1024;
    unsigned major = 3, minor = 1;
    NtfsStreamJoinLimits limits;
};
struct NtfsFilename {
    std::uint64_t reference = 0, parent_reference = 0;
    unsigned instance = 0, resident_flags = 0, namespace_code = 0;
    std::vector<unsigned char> name, value;
};
struct NtfsFilenamesResult {
    // Nonnull only for a complete supplied inventory, including an empty one.
    std::unique_ptr<const std::vector<NtfsFilename>> names;
    std::vector<std::uint64_t> required_records;
    json::Value observation;
};
NtfsFilenamesResult collect_ntfs_filenames(const NtfsFilenameRequest &,
                                           const std::vector<NtfsCapturedRecord> &,
                                           const NtfsCapturedAttributeList * = nullptr);
} // namespace disked
