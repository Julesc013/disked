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
class NamespaceFrameSnapshot final {
    const json::Value value_,context_;
    const CaptureKey key_;
    const std::string frame_digest_,context_digest_;
    NamespaceFrameSnapshot(json::Value value,json::Value context,CaptureKey key):value_(std::move(value)),context_(std::move(context)),key_(std::move(key)),
        frame_digest_(digest_sha256(json::dump(value_,volume_inventory_limits()))),context_digest_(digest_sha256(json::dump(context_))){}
    friend class NamespaceGraphAdapter;
public:
    const json::Value& value()const{return value_;}
    const json::Value& context()const{return context_;}
    const CaptureKey& key()const{return key_;}
    const std::string& frame_digest()const{return frame_digest_;}
    const std::string& context_digest()const{return context_digest_;}
};
class NamespaceGraphEvidence final {
    const std::shared_ptr<const NamespaceFrameSnapshot> current_,last_complete_;
    NamespaceGraphEvidence(std::shared_ptr<const NamespaceFrameSnapshot> current,std::shared_ptr<const NamespaceFrameSnapshot> complete):
        current_(std::move(current)),last_complete_(std::move(complete)){}
    friend class NamespaceGraphAdapter;
public:
    std::shared_ptr<const NamespaceFrameSnapshot> current()const{return current_;}
    std::shared_ptr<const NamespaceFrameSnapshot> last_complete()const{return last_complete_;}
};

class NamespaceGraphAdapter final {
    ObservationCapture& capture_;std::string source_;
    CaptureKey key_;std::unique_ptr<NamespaceWorker> session_;
    json::Value context_;InventoryPolicy policy_;
    GraphInput previous_complete_;bool have_previous_complete_=false;
    std::shared_ptr<const NamespaceGraphEvidence> frames_;
    void consume(const json::Value&);
public:
    NamespaceGraphAdapter(ObservationCapture&,std::string source);
    void start(const InventoryPolicy&,const json::Value& fixture);
    void release();void cancel();bool timeout();bool wait_entered(DWORD);
    json::Value poll(DWORD wait_ms=0);
    json::Value retire(DWORD wait_ms=2000);
    const CaptureKey& key() const {return key_;}
    std::shared_ptr<const NamespaceGraphEvidence> frames()const{return frames_;}
};
}}
