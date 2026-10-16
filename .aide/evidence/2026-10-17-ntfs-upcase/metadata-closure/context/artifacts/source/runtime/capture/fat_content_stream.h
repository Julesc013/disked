#pragma once
#include "fat_traversal.h"
#include <array>

namespace disked {
struct FatContentStreamSelection {
    FatTraversalBinding binding;
    std::uint64_t record_source_offset = 0;
    std::array<unsigned char, 32> record{};
};
struct FatContentStreamBudget {
    std::size_t bytes = 65536, reads = 256, read_bytes = 196608, cells = 256;
    std::size_t output_bytes = 1048576;
};
struct FatContentStreamError : std::runtime_error {
    explicit FatContentStreamError(const char *code) : std::runtime_error(code) {
    }
};
// Private supplied-reader continuation. Exact record matching is neither
// directory-membership authentication nor a native source-opening grant.
// Retains one chain bitmap/current cluster and copied bounded page bytes.
class FatContentStream final {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    FatContentStream(const FatContentStreamSelection &, const FatTraversalPort &,
                     std::size_t bitmap_bytes = 67108864);
    ~FatContentStream();
    FatContentStream(const FatContentStream &) = delete;
    FatContentStream &operator=(const FatContentStream &) = delete;
    json::Value next(const FatContentStreamSelection &,
                     const FatContentStreamBudget & = FatContentStreamBudget{});
    bool finished() const;
};
} // namespace disked
