#pragma once
#include "storage_worker.h"
#include "storage_identity.h"
namespace disked { namespace nt_inventory {
json::Value storage_graph_context(const json::Value&,StorageFrameProfile profile=StorageFrameProfile::Metadata);
enum class StorageGraphProjection {Frame,Identity};
struct StorageComparisonSelection {std::string previous_digest,previous_subject,current_subject;};
class StorageGraphEvidence final {
    const std::shared_ptr<const StorageIdentityProjection> current_,last_complete_;
    StorageGraphEvidence(std::shared_ptr<const StorageIdentityProjection> current,std::shared_ptr<const StorageIdentityProjection> complete):
        current_(std::move(current)),last_complete_(std::move(complete)){}
    friend class StorageGraphAdapter;
public:
    std::shared_ptr<const StorageIdentityProjection> current()const{return current_;}
    std::shared_ptr<const StorageIdentityProjection> last_complete()const{return last_complete_;}
    // Complete retained data; neither this accessor nor resolution polls a reader.
    const json::Value& resolve(const std::string& kind,const std::string& digest)const;
};
class StorageGraphAdapter final{
    ObservationCapture& capture_;std::string source_;CaptureKey key_;std::unique_ptr<StorageWorker> session_;
    StorageInput input_;json::Value context_;GraphInput previous_complete_;bool have_previous_complete_=false;
    const StorageFrameProfile profile_;
    const StorageGraphProjection projection_;
    std::shared_ptr<const StorageGraphEvidence> evidence_;
    std::shared_ptr<const StorageIdentityProjection> comparison_previous_;
    std::vector<StorageComparisonSelection> comparisons_;
    void consume(const json::Value&);
public:
    StorageGraphAdapter(ObservationCapture&,std::string source,StorageFrameProfile profile=StorageFrameProfile::Metadata,
        StorageGraphProjection projection=StorageGraphProjection::Frame);
    void start(const StorageQueryPolicy&,const json::Value& fixture,const std::vector<StorageComparisonSelection>& comparisons={});void release();void cancel();bool timeout();bool wait_entered(DWORD);
    json::Value poll(DWORD wait_ms=0);json::Value retire(DWORD wait_ms=2000);const CaptureKey& key() const{return key_;}
    // Current accepted capture from this actual owned adapter, never from JSON.
    std::shared_ptr<const StorageFrameSnapshot> frame();
    std::shared_ptr<const StorageGraphEvidence> evidence()const{return evidence_;}
};
}}
