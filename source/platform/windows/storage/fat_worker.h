#pragma once
#include "observation_worker.h"
#include "providers/image/fat_snapshot.h"

namespace disked {
namespace nt_inventory {
class FatWorker final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit FatWorker(std::unique_ptr<Impl>);

  public:
    ~FatWorker();
    FatWorker(const FatWorker &) = delete;
    FatWorker &operator=(const FatWorker &) = delete;
    static std::unique_ptr<FatWorker> prepare(const FatSnapshotInput &);
    void launch();
    void release();
    void cancel();
    bool never_launched() const;
    bool wait_entered(DWORD);
    json::Value observe(DWORD wait_ms = 0);
    json::Value retire(DWORD wait_ms = 2000);
    std::shared_ptr<const FatFileSnapshot> snapshot();
};
int fat_worker_role(int, wchar_t **);
} // namespace nt_inventory
} // namespace disked
