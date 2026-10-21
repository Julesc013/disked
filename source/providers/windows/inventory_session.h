#pragma once
#include "namespace_graph.h"
#include "storage_graph.h"

namespace disked { namespace nt_inventory {
class InventorySession;
class InventoryPublication final {
    const std::shared_ptr<const CaptureView> view_;
    const std::shared_ptr<const NamespaceGraphEvidence> namespace_;
    const std::shared_ptr<const StorageFrameEvidence> storage_;
    const std::shared_ptr<const StorageGraphEvidence> identity_;
    InventoryPublication(std::shared_ptr<const CaptureView>,std::shared_ptr<const NamespaceGraphEvidence>,
        std::shared_ptr<const StorageFrameEvidence>,std::shared_ptr<const StorageGraphEvidence>);
    friend class InventorySession;
    const GraphNode& node(const std::string&)const;
public:
    std::shared_ptr<const CaptureView> view()const{return view_;}
    // Exact complete retained data; no polling, path lookup or storage grant.
    const json::Value& frame(const std::string& node_id)const;
    const json::Value& resolve(const std::string& node_id,const std::string& reference_name)const;
};
struct InventoryPortState;
class InventoryPort final {
    const std::shared_ptr<const InventoryPortState> state_;
    explicit InventoryPort(std::shared_ptr<const InventoryPortState> state):state_(std::move(state)){}
    friend class InventorySession;
public:
    // Serialized readonly access. Port and graph owners may outlive the session.
    std::shared_ptr<const GraphInput> graph()const;
    std::shared_ptr<const InventoryPublication> publication()const;
};
enum class InventorySource {Namespace,Storage};
class InventorySession final {
    ObservationCapture capture_;
    NamespaceGraphAdapter namespace_;
    StorageGraphAdapter storage_;
    std::shared_ptr<InventoryPortState> state_;
public:
    explicit InventorySession(StorageFrameProfile profile=StorageFrameProfile::Metadata,StorageGraphProjection projection=StorageGraphProjection::Frame,NamespaceBackend backend=NamespaceBackend::Injected);
    InventorySession(const InventorySession&)=delete;
    InventorySession& operator=(const InventorySession&)=delete;
    void next_capture(){capture_.next_capture();}
    void start_namespace(const InventoryPolicy& policy,const json::Value& fixture){namespace_.start(policy,fixture);}
    void start_native_namespace(const InventoryPolicy& policy){namespace_.start_native(policy);}
    void start_storage(const StorageQueryPolicy& policy,const json::Value& fixture,const std::vector<StorageComparisonSelection>& selections={}){storage_.start(policy,fixture,selections);}
    void release(InventorySource);void cancel(InventorySource);bool timeout(InventorySource);bool wait_entered(InventorySource,DWORD);
    json::Value poll(InventorySource,DWORD wait_ms=0);json::Value retire(InventorySource,DWORD wait_ms=2000);
    std::shared_ptr<const CaptureView> capture()const{return capture_.snapshot();}
    bool publish();bool needs_publication()const;
    InventoryPort port()const{return InventoryPort(state_);}
};
}}
