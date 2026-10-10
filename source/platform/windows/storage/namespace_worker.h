#pragma once
#include "volume_inventory.h"
#include <memory>
namespace disked { namespace nt_inventory {
struct NamespaceInput {std::uint64_t capture_epoch=0;InventoryPolicy policy;json::Value provider_input;};
// Temporary owned injected-reader session. No durable operation/public ABI,
// native storage dispatch, writer port or arbitrary executable selection.
class NamespaceWorker final {
    struct Impl;std::unique_ptr<Impl> impl_;
    explicit NamespaceWorker(std::unique_ptr<Impl>);
public:
    ~NamespaceWorker();
    NamespaceWorker(const NamespaceWorker&)=delete;
    NamespaceWorker& operator=(const NamespaceWorker&)=delete;
    static std::unique_ptr<NamespaceWorker> start(const NamespaceInput&);
    json::Value observe(DWORD wait_ms=0);
    void release();
    void cancel();
    json::Value retire(DWORD wait_ms=2000);
    bool wait_entered(DWORD wait_ms);
};
using VolumeFactory=std::function<VolumeApi(const json::Value&,const std::function<void()>&)>;
int namespace_worker_role(int argc,wchar_t** argv,const VolumeFactory&);
json::Limits namespace_worker_limits();
// Producer conformance only, not provenance, process exit or provider admission.
void validate_namespace_snapshot(const json::Value&,std::uint64_t,const InventoryPolicy&);
void validate_namespace_input(const NamespaceInput&);
}}
