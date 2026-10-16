#pragma once
#include "exfat_upcase.h"
#include <array>
#include <cstdint>
#include <vector>

namespace disked {
struct ExfatDirectoryRecord {
    std::uint64_t source_offset = 0;
    std::array<unsigned char, 32> bytes{};
};
struct ExfatNamespaceDirectory {
    std::size_t id = 0;
    bool root = false, extent_complete = false;
    std::vector<ExfatDirectoryRecord> records;
};
struct ExfatNameQuery {
    std::size_t directory = 0;
    std::vector<unsigned short> units;
};
struct ExfatNamespaceLimits {
    std::size_t directories = 256, records = 4096, queries = 256;
    std::size_t comparisons = 65536, findings = 128, output_bytes = 1048576;
};
// Supplied capture facts only. No source opening, path resolution, allocation
// membership, current-source permission, effect or physical authority.
json::Value observe_exfat_namespace(const std::vector<ExfatNamespaceDirectory> &,
                                    const ExfatUpcaseMap &, const std::vector<ExfatNameQuery> &,
                                    std::uint32_t clusters, unsigned cluster_shift,
                                    const ExfatNamespaceLimits & = ExfatNamespaceLimits{},
                                    bool capture_applicable = true);
} // namespace disked
