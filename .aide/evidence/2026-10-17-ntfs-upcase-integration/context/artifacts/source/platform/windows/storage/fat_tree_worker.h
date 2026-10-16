#pragma once
#include "observation_worker.h"
#include "providers/image/fat_tree_snapshot.h"

namespace disked {
namespace nt_inventory {
// Compiled bounded page adapter over the existing process host. Each returned
// page is copied, reconstructed and bound to this actual owned session.
class FatTreeWorker final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit FatTreeWorker(std::unique_ptr<Impl>);

  public:
    ~FatTreeWorker();
    FatTreeWorker(const FatTreeWorker &) = delete;
    FatTreeWorker &operator=(const FatTreeWorker &) = delete;
    static std::unique_ptr<FatTreeWorker> prepare(const FatTreeInput &);
    void launch();
    void release();
    void cancel();
    bool never_launched() const;
    bool wait_entered(DWORD);
    std::shared_ptr<const FatTreePage> next_page();
    json::Value observe(DWORD wait_ms = 0);
    json::Value retire(DWORD wait_ms = 2000);
};
int fat_tree_worker_role(int, wchar_t **);
} // namespace nt_inventory
} // namespace disked
