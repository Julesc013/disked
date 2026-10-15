#pragma once
#include "observation_worker.h"
#include "providers/image/ntfs_snapshot.h"

namespace disked {
namespace nt_inventory {
class NtfsWorker final {
    struct Impl;
    std::unique_ptr<Impl> impl_;
    explicit NtfsWorker(std::unique_ptr<Impl>);

  public:
    ~NtfsWorker();
    NtfsWorker(const NtfsWorker &) = delete;
    NtfsWorker &operator=(const NtfsWorker &) = delete;
    static std::unique_ptr<NtfsWorker> prepare(const NtfsSnapshotInput &);
    void launch();
    void release();
    void cancel();
    bool never_launched() const;
    bool wait_entered(DWORD);
    json::Value observe(DWORD wait_ms = 0);
    json::Value retire(DWORD wait_ms = 2000);
    std::shared_ptr<const NtfsFileSnapshot> snapshot(bool retain_frame = false);
};
int ntfs_worker_role(int, wchar_t **);
} // namespace nt_inventory
} // namespace disked
