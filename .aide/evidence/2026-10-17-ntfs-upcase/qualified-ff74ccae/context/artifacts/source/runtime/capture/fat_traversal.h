#pragma once
#include "region_reader.h"
#include "runtime/command/json.h"
#include <cstdint>
#include <memory>
#include <string>

namespace disked {
struct FatTraversalBinding {
    std::string source_id, capture_id;
    std::uint64_t epoch = 0, source_bytes = 0, volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0;
};
struct FatTraversalResources {
    std::size_t bitmap_bytes = 67108864, queued_directories = 65536, depth = 1024;
};
struct FatTraversalPageBudget {
    std::size_t records = 256, events = 256, reads = 512;
    std::size_t read_bytes = 65536, output_bytes = 65536;
};
struct FatTraversalPort {
    // Read views are copied before the next callback; none survive in state.
    RegionReader read;
    // Mandatory provider observation, not an authentication/atomicity proof.
    // The caller keeps its selected view immutable while this binding applies.
    std::function<bool(const FatTraversalBinding &)> applicable;
};
struct FatTraversalError : std::runtime_error {
    explicit FatTraversalError(const char *code) : std::runtime_error(code) {
    }
};
// Hash the canonical page body without its page_digest, in the established
// private traversal domain. This does not authenticate source or process data.
std::string fat_traversal_page_digest(const json::Value &page_body);
// Private supplied-region directory traversal. This never opens a source or
// interprets a path. Owns continuation and copied metadata; no borrowed views
// escape. No trusted serialized continuation or extraction grant is produced.
class FatTraversal {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    FatTraversal(const FatTraversalBinding &, const FatTraversalPort &,
                 const FatTraversalResources & = FatTraversalResources{});
    ~FatTraversal();
    FatTraversal(const FatTraversal &) = delete;
    FatTraversal &operator=(const FatTraversal &) = delete;
    FatTraversal(FatTraversal &&) noexcept;
    FatTraversal &operator=(FatTraversal &&) noexcept;
    json::Value next(const FatTraversalBinding &,
                     const FatTraversalPageBudget & = FatTraversalPageBudget{});
    bool finished() const;
};
} // namespace disked
