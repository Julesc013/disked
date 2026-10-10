#pragma once
#include "storage_worker.h"
namespace disked { namespace nt_inventory {
json::Value storage_graph_context(const json::Value&,StorageFrameProfile profile=StorageFrameProfile::Metadata);
class StorageGraphAdapter final{
    ObservationCapture& capture_;std::string source_;CaptureKey key_;std::unique_ptr<StorageWorker> session_;
    StorageInput input_;json::Value context_;GraphInput previous_complete_;bool have_previous_complete_=false;
    const StorageFrameProfile profile_;
    void consume(const json::Value&);
public:
    StorageGraphAdapter(ObservationCapture&,std::string source,StorageFrameProfile profile=StorageFrameProfile::Metadata);
    void start(const StorageQueryPolicy&,const json::Value& fixture);void release();void cancel();bool timeout();bool wait_entered(DWORD);
    json::Value poll(DWORD wait_ms=0);json::Value retire(DWORD wait_ms=2000);const CaptureKey& key() const{return key_;}
};
}}
