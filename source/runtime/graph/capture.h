#pragma once
#include "snapshot.h"
#include <deque>
#include <map>

namespace disked {
class ObservationCapture;
// A local counter domain, never a serialized credential or media identity.
class CaptureEpochDomain final {
    const std::uint64_t ordinal_;
    explicit CaptureEpochDomain(std::uint64_t ordinal):ordinal_(ordinal){}
    friend class ObservationCapture;
public:
    CaptureEpochDomain(const CaptureEpochDomain&)=delete;
    CaptureEpochDomain& operator=(const CaptureEpochDomain&)=delete;
    CaptureEpochDomain(CaptureEpochDomain&&)=delete;
    CaptureEpochDomain& operator=(CaptureEpochDomain&&)=delete;
    std::uint64_t local_ordinal()const{return ordinal_;}
};
// Private serialized observation contract. Adapters own processes/threads and
// supply retirement evidence; this reducer has no effect or worker authority.
struct CaptureKey {
    std::string source;
    std::uint64_t capture=0,worker=0;
    std::shared_ptr<const CaptureEpochDomain> domain;
    bool operator==(const CaptureKey& other) const {
        return domain==other.domain && source==other.source && capture==other.capture && worker==other.worker;
    }
};
enum class SourceState {NotStarted,Pending,Complete,Partial,Denied,Malformed,Unavailable,TimedOut};
const char* source_state_name(SourceState state);
struct CaptureSource {
    std::string id;
    SourceState state=SourceState::NotStarted;
    bool outstanding=false;
    CaptureKey attempt;
    std::string reason,platform;
};
struct CaptureNotice {
    std::uint64_t sequence=0,capture=0;
    CaptureSource source;
};
struct CaptureView {
    std::uint64_t capture=0,sequence=0;
    GraphInput graph;
    std::vector<CaptureSource> sources;
};
struct CaptureChanges {
    bool resnapshot=false;
    std::vector<CaptureNotice> notices;
    std::shared_ptr<const CaptureView> current;
};
class ObservationCapture final {
public:
    explicit ObservationCapture(const std::vector<std::string>& sources,GraphProfile profile=GraphProfile::Fake);
    ObservationCapture(const ObservationCapture&)=delete;
    ObservationCapture& operator=(const ObservationCapture&)=delete;
    ObservationCapture(ObservationCapture&&)=delete;
    ObservationCapture& operator=(ObservationCapture&&)=delete;
    std::shared_ptr<const CaptureEpochDomain> epoch_domain()const{return domain_;}
    std::shared_ptr<const CaptureView> snapshot() const {return view_;}
    CaptureKey start(const std::string& source);
    bool timeout(const CaptureKey& key);
    // Publication and worker lifetime are independent. These methods require a
    // current matching attempt and never clear outstanding, even on bad input.
    // Partial content has an explicit omission; individual current rows stay
    // current. Adapters must mark any carried-forward rows stale themselves.
    bool update(const CaptureKey& key,const GraphInput& graph,SourceState state=SourceState::Complete,
        const std::string& reason="",const std::string& platform="");
    bool update_failure(const CaptureKey& key,SourceState state,const std::string& reason,const std::string& platform="");
    // Only an adapter that observed retirement of this exact owned attempt may
    // call this. A result, timeout or cancellation request is not that evidence.
    // Superseded results are discarded without permitting early replacement.
    bool retired(const CaptureKey& key);
    // Legacy atomic publication + retirement: finish()/fail() are called only
    // after the adapter observed this exact attempt retire. They never prove a
    // storage operation quiescent or reusable. Use update() for a live worker.
    // Its boolean means state changed, including rejected/stale completions;
    // inspect the source state to determine whether content was accepted.
    bool finish(const CaptureKey& key,const GraphInput& graph);
    bool fail(const CaptureKey& key,SourceState state,const std::string& reason,const std::string& platform="");
    void next_capture();
    CaptureChanges changes(std::uint64_t capture,std::uint64_t after) const;
private:
    std::shared_ptr<const CaptureEpochDomain> domain_;
    struct Slot {
        CaptureSource visible;
        GraphInput retained;
        std::string retained_revision;
        std::uint64_t last_worker=0,started_capture=0;
        bool has_retained=false;
    };
    struct Identity {std::string owner,identity,generation;};
    struct State {
        GraphProfile profile=GraphProfile::Fake;
        std::uint64_t capture=1,sequence=0,capture_start=0;
        std::vector<Slot> slots;
        std::map<std::string,Identity> identities;
        std::deque<CaptureNotice> notices;
    } state_;
    std::shared_ptr<const CaptureView> view_;
    std::size_t slot(const std::string& source) const;
    bool matches(std::size_t index,const CaptureKey& key) const;
    GraphInput aggregate(const State& state) const;
    bool retire_old(State& next,std::size_t index,const CaptureKey& key);
    void stage(State& next,std::size_t index,const CaptureKey& key,const GraphInput& graph,
        SourceState state,const std::string& reason,const std::string& platform,bool retire);
    void publish(State next,std::size_t changed);
};
}
