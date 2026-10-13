#pragma once
#include "region_reader.h"
#include "runtime/command/json.h"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace disked {
struct FatContentBinding {
    std::string source_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0;
};
struct FatContentLimits {
    std::size_t bytes = 196608, read_requests = 512, read_chunk = 4096;
};
struct FatContentError : std::runtime_error {
    std::string code;
    explicit FatContentError(const char *name) : std::runtime_error(name), code(name) {
    }
};

// Private validated mapping over supplied metadata. It does not authenticate a
// native source, establish freshness, or admit a public extraction operation.
class FatContentMap {
    struct Extent {
        std::uint64_t source = 0, file = 0, content = 0;
    };
    FatContentBinding binding_;
    std::vector<Extent> extents_;
    std::uint64_t node_ = 0, file_bytes_ = 0;
    bool tree_complete_ = false, metadata_consistent_ = false;
    bool cross_link_ = false, excess_allocation_ = false;
    FatContentMap() = default;
    friend FatContentMap prepare_fat_content(const json::Value &, std::uint64_t,
                                             const FatContentBinding &);

  public:
    std::uint64_t file_bytes() const {
        return file_bytes_;
    }
    json::Value read(std::uint64_t offset, std::size_t count, const RegionReader &,
                     FatContentLimits limits = {}) const;
};
FatContentMap prepare_fat_content(const json::Value &observation, std::uint64_t node_id,
                                  const FatContentBinding &expected);
} // namespace disked
