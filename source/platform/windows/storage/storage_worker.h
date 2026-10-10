#pragma once
#include "observation_worker.h"
#include "storage_frame_reader.h"
namespace disked { namespace nt_inventory {
struct StorageInput{std::uint64_t capture_epoch=0;StorageQueryPolicy policy;json::Value provider_input;};
class StorageWorker final{
    std::unique_ptr<ObservationWorker> worker_;explicit StorageWorker(std::unique_ptr<ObservationWorker> p):worker_(std::move(p)){}
public:
    static std::unique_ptr<StorageWorker> prepare(const StorageInput&);
    void launch(){worker_->launch();}bool never_launched() const{return worker_->never_launched();}
    void release(){worker_->release();}void cancel(){worker_->cancel();}bool wait_entered(DWORD n){return worker_->wait_entered(n);}
    json::Value observe(DWORD n=0){return worker_->observe(n);}json::Value retire(DWORD n=2000){return worker_->retire(n);}
};
using StorageFactory=std::function<StorageQueryApi(const json::Value&,const std::function<void()>&)>;
int storage_worker_role(int,wchar_t**,const StorageFactory&);
json::Limits storage_worker_limits();void validate_storage_input(const StorageInput&);
}}
