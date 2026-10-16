#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include "providers/image/fat_tree_extraction.h"
#include "runtime/acquisition/fat_tree_review.h"

namespace disked {
namespace nt_inventory {
struct FatTreeStoreError : std::runtime_error {
    DWORD platform_code;
    explicit FatTreeStoreError(const char *code, DWORD platform = 0)
        : std::runtime_error(code), platform_code(platform) {
    }
};
// Actual pinned ordinary NTFS directory. Constructor/observation create nothing.
// Reserved children are create-only; partial initialization is never erased.
class FatTreeStore final {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    FatTreeStore(const std::string &, const FatTreeExtractionRequest &);
    ~FatTreeStore();
    FatTreeStore(const FatTreeStore &) = delete;
    FatTreeStore &operator=(const FatTreeStore &) = delete;
    json::Value observation() const;
    void check_unused() const;
    void reserve(const FatTreeReview &, const FatTreeReviewGrant &, const std::string &operation,
                 const json::Value &process_owner, const std::string &process_digest);
    // Exact process observation is supplied by the existing owned worker.
    void bind_writer(const json::Value &);
    void append_state(const char *phase, const json::Value &worker);
    void request_cancel();
    bool cancellation_requested() const;
    bool effects_possible() const;
    bool reserved() const;
    const std::string &operation_id() const;
    std::size_t state_records() const;
};
} // namespace nt_inventory
} // namespace disked
