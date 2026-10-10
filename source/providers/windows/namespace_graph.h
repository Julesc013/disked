#pragma once
#include "capture.h"
#include "namespace_worker.h"

namespace disked { namespace nt_inventory {
struct NamespaceGraphBinding {
    CaptureKey key;
    json::Value worker_context;
    InventoryPolicy policy;
};
// Pure projection of conforming data. This function authenticates no producer
// and observes no process. The owned adapter supplies those separate bindings.
GraphInput project_namespace_snapshot(const json::Value&,const NamespaceGraphBinding&);
json::Value namespace_graph_context(const json::Value& worker_observation);

class NamespaceGraphAdapter final {
    ObservationCapture& capture_;std::string source_;
    CaptureKey key_;std::unique_ptr<NamespaceWorker> session_;
    json::Value context_;InventoryPolicy policy_;
    GraphInput previous_complete_;bool have_previous_complete_=false;
    void consume(const json::Value&);
public:
    NamespaceGraphAdapter(ObservationCapture&,std::string source);
    void start(const InventoryPolicy&,const json::Value& fixture);
    void release();void cancel();bool timeout();bool wait_entered(DWORD);
    json::Value poll(DWORD wait_ms=0);
    json::Value retire(DWORD wait_ms=2000);
    const CaptureKey& key() const {return key_;}
};
}}
