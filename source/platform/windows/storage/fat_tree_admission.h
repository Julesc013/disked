#pragma once
#include "fat_tree_store.h"
#include "fat_tree_extraction_worker.h"

namespace disked {
namespace nt_inventory {
// Private serialized caller-owned controller. Native facts are independently
// prepared; copied/imported definitions cannot mint a prepared worker artifact.
class FatTreeAdmission final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit FatTreeAdmission(std::unique_ptr<Impl>);

  public:
    ~FatTreeAdmission();
    FatTreeAdmission(const FatTreeAdmission &) = delete;
    FatTreeAdmission &operator=(const FatTreeAdmission &) = delete;
    static std::unique_ptr<FatTreeAdmission>
    prepare(const FatTreeExtractionRequest &, const std::string &store,
            const json::Value &fixture = json::Value::object());
    // Validate review/grants before touching any native path. Launch still
    // performs no output; dispatch waits for fresh comparison and reservation.
    static std::unique_ptr<FatTreeAdmission>
    for_execution(const FatTreeReview &, const FatTreeReviewGrant &,
                  const json::Value &fixture = json::Value::object());
    void launch();
    json::Value observe(DWORD wait_ms = 0);
    std::shared_ptr<const FatTreeReview> prepared_review() const;
    void grant(const FatTreeReview &, const FatTreeReviewGrant &);
    void cancel();
    json::Value retire(DWORD wait_ms = 2000);
};
} // namespace nt_inventory
} // namespace disked
