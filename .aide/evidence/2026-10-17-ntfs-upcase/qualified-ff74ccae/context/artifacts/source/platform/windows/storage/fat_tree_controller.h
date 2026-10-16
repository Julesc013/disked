#pragma once
#include "runtime/acquisition/fat_tree_review.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <memory>

namespace disked {
namespace nt_inventory {
// Private explicit dispatch handoff. Destroying a dispatched client does not
// cancel the independently owned controller or authorize another writer.
class FatTreeController final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit FatTreeController(std::unique_ptr<Impl>);

  public:
    ~FatTreeController();
    FatTreeController(const FatTreeController &) = delete;
    FatTreeController &operator=(const FatTreeController &) = delete;
    static std::unique_ptr<FatTreeController>
    prepare(const FatTreeReview &, const FatTreeReviewGrant &,
            const json::Value &fixture = json::Value::object());
    void launch();
    void dispatch();
    json::Value observe(DWORD wait_ms = 0);
};
int fat_tree_controller_role(int argc, wchar_t **argv);
} // namespace nt_inventory
} // namespace disked
