#pragma once
#include "observation_worker.h"
#include "providers/image/exfat_snapshot.h"

namespace disked {
namespace nt_inventory {
class ExfatWorker final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit ExfatWorker(std::unique_ptr<Impl>);

  public:
    ~ExfatWorker();
    ExfatWorker(const ExfatWorker &) = delete;
    ExfatWorker &operator=(const ExfatWorker &) = delete;
    static std::unique_ptr<ExfatWorker> prepare(const ExfatSnapshotInput &);
    void launch();
    void release();
    void cancel();
    bool never_launched() const;
    bool wait_entered(DWORD);
    json::Value observe(DWORD wait_ms = 0);
    json::Value retire(DWORD wait_ms = 2000);
    std::shared_ptr<const ExfatFileSnapshot> snapshot(bool retain_frame = false);
};
int exfat_worker_role(int, wchar_t **);
} // namespace nt_inventory
} // namespace disked
