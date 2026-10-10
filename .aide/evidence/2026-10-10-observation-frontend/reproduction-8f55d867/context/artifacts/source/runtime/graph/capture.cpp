#include "capture.h"
#include <limits>
#include <set>

namespace disked {
namespace {
void require(bool value,const char* reason) {if(!value)throw std::invalid_argument(reason);}
bool identifier(const std::string& value) {
    if(value.empty() || value.size()>64)return false;
    for(const auto c:value)if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') ||
        c=='.' || c=='_' || c=='-' || c=='/'))return false;
    return true;
}
void increment(std::uint64_t& value) {
    require(value!=(std::numeric_limits<std::uint64_t>::max)(),"capture_counter_limit");++value;
}
}
const char* source_state_name(SourceState state) {
    switch(state) {
    case SourceState::NotStarted:return "not_started";
    case SourceState::Pending:return "pending";
    case SourceState::Complete:return "complete";
    case SourceState::Partial:return "partial";
    case SourceState::Denied:return "denied";
    case SourceState::Malformed:return "malformed";
    case SourceState::Unavailable:return "unavailable";
    case SourceState::TimedOut:return "timed_out";
    }
    throw std::invalid_argument("capture_invalid_state");
}
ObservationCapture::ObservationCapture(const std::vector<std::string>& sources,GraphProfile profile) {
    graph_limits(profile);state_.profile=profile;
    require(!sources.empty() && sources.size()<=8,"capture_source_limit");std::set<std::string> unique;
    for(const auto& id:sources) {
        require(identifier(id) && unique.insert(id).second,"capture_source_invalid");
        Slot value;value.visible.id=id;value.visible.attempt.source=id;state_.slots.push_back(value);
    }
    // Sequence zero is the initial snapshot, before any attempted observation.
    auto view=std::make_shared<CaptureView>();view->capture=state_.capture;view->graph=aggregate(state_);
    for(const auto& item:state_.slots)view->sources.push_back(item.visible);view_=view;
}
std::size_t ObservationCapture::slot(const std::string& source) const {
    for(std::size_t i=0;i<state_.slots.size();++i)if(state_.slots[i].visible.id==source)return i;
    throw std::invalid_argument("capture_source_unknown");
}
bool ObservationCapture::matches(std::size_t index,const CaptureKey& key) const {
    const auto& current=state_.slots[index].visible;return current.outstanding && current.attempt==key;
}
GraphInput ObservationCapture::aggregate(const State& state) const {
    GraphInput graph;graph.profile=state.profile;
    for(const auto& item:state.slots) {
        if(item.has_retained) {
            for(auto node:item.retained.nodes) {
                if(item.visible.state!=SourceState::Complete && item.visible.state!=SourceState::Partial &&
                    (node.state=="current" || (node.scope==GraphNodeScope::Observation && node.state=="unknown")))node.state="stale";
                graph.nodes.push_back(std::move(node));
            }
            graph.edges.insert(graph.edges.end(),item.retained.edges.begin(),item.retained.edges.end());
            graph.omissions.insert(graph.omissions.end(),item.retained.omissions.begin(),item.retained.omissions.end());
        }
        if(item.visible.state!=SourceState::Complete) {
            std::string omission=item.visible.id+":"+source_state_name(item.visible.state);
            if(!item.visible.reason.empty())omission+=":"+item.visible.reason;
            if(!item.visible.platform.empty())omission+=":"+item.visible.platform;
            graph.omissions.push_back(std::move(omission));
        }
    }
    return graph;
}
void ObservationCapture::publish(State next,std::size_t changed) {
    increment(next.sequence);
    auto view=std::make_shared<CaptureView>();view->capture=next.capture;view->sequence=next.sequence;
    view->graph=aggregate(next);GraphSnapshot::create(view->graph,next.capture);
    for(const auto& item:next.slots)view->sources.push_back(item.visible);
    CaptureNotice notice;notice.sequence=next.sequence;notice.capture=next.capture;
    // A capture reset is signalled with source.id empty; it always requires a
    // fresh snapshot for a reader still bound to the previous capture epoch.
    if(changed<next.slots.size())notice.source=next.slots[changed].visible;
    next.notices.push_back(std::move(notice));if(next.notices.size()>8)next.notices.pop_front();
    // Throwing copy/validation/allocation work precedes these no-throw swaps.
    std::swap(state_.capture,next.capture);std::swap(state_.sequence,next.sequence);
    std::swap(state_.capture_start,next.capture_start);
    state_.slots.swap(next.slots);state_.identities.swap(next.identities);state_.notices.swap(next.notices);
    std::shared_ptr<const CaptureView> immutable=view;view_.swap(immutable);
}
CaptureKey ObservationCapture::start(const std::string& source) {
    const auto at=slot(source);const auto& before=state_.slots[at];
    require(!before.visible.outstanding,"capture_worker_outstanding");
    require(before.started_capture!=state_.capture,"capture_attempt_already_started");
    State next=state_;auto& item=next.slots[at];increment(item.last_worker);item.started_capture=next.capture;
    item.visible.state=SourceState::Pending;item.visible.outstanding=true;item.visible.reason.clear();item.visible.platform.clear();
    item.visible.attempt={source,next.capture,item.last_worker};const auto key=item.visible.attempt;
    publish(std::move(next),at);return key;
}
bool ObservationCapture::timeout(const CaptureKey& key) {
    const auto at=slot(key.source);if(!matches(at,key) || key.capture!=state_.capture || state_.slots[at].visible.state==SourceState::TimedOut)return false;
    State next=state_;auto& visible=next.slots[at].visible;visible.state=SourceState::TimedOut;visible.reason="probe_wait_expired";
    publish(std::move(next),at);return true;
}
bool ObservationCapture::retire_old(State& next,std::size_t at,const CaptureKey& key) {
    if(key.capture==next.capture)return false;
    auto& visible=next.slots[at].visible;visible.outstanding=false;visible.state=SourceState::NotStarted;
    visible.reason="superseded_result_discarded";visible.platform.clear();return true;
}
bool ObservationCapture::fail(const CaptureKey& key,SourceState failure,const std::string& reason,const std::string& platform) {
    require(failure==SourceState::Denied || failure==SourceState::Malformed || failure==SourceState::Unavailable,"capture_invalid_failure");
    require(identifier(reason) && (platform.empty() || json::decimal_u64(platform)),"capture_invalid_reason");
    const auto at=slot(key.source);if(!matches(at,key))return false;
    State next=state_;
    if(!retire_old(next,at,key)) {
        auto& visible=next.slots[at].visible;visible.outstanding=false;visible.state=failure;visible.reason=reason;visible.platform=platform;
    }
    publish(std::move(next),at);return true;
}
void ObservationCapture::stage(State& next,std::size_t at,const CaptureKey& key,const GraphInput& graph,
    SourceState state,const std::string& reason,const std::string& platform,bool retire) {
    require(next.profile==GraphProfile::Observations || graph.profile==GraphProfile::Fake,"capture_profile_invalid");
    const auto snapshot=GraphSnapshot::create(graph,next.capture);
    for(const auto& node:graph.nodes) {
        if(node.scope==GraphNodeScope::Observation) {
            const auto& o=node.observation;
            require(o.source==key.source && o.capture<=key.capture && o.worker<=key.worker &&
                (o.capture==key.capture?(o.worker==key.worker):(node.state=="stale" && o.worker<key.worker)),"capture_observation_binding");
            // Content-bound observation IDs carry source/attempt ownership.
            // They are not lifetime media-identity tombstones.
            continue;
        }
        const auto found=next.identities.find(node.id);
        if(found!=next.identities.end())require(found->second.owner==key.source && found->second.identity==node.identity &&
            found->second.generation==node.media_generation,"capture_identity_reuse");
        next.identities[node.id]={key.source,node.identity,node.media_generation};
    }
    require(next.identities.size()<=1024,"capture_identity_limit");
    auto& item=next.slots[at];item.retained=graph;item.retained_revision=snapshot->revision();item.has_retained=true;
    item.visible.state=state;item.visible.outstanding=!retire;item.visible.reason=reason;item.visible.platform=platform;
    std::size_t omissions=0;for(const auto& source:next.slots)omissions+=source.retained.omissions.size();
    require(omissions<=48,"capture_omission_limit");
    const auto validated=GraphSnapshot::create(aggregate(next),next.capture);
    const auto limits=graph_limits(next.profile);
    require(json::dump(validated->value(),limits).size()<=limits.bytes-8192,"capture_graph_limit");
}
bool ObservationCapture::update(const CaptureKey& key,const GraphInput& graph,SourceState state,
    const std::string& reason,const std::string& platform) {
    require(state==SourceState::Complete || state==SourceState::Partial,"capture_invalid_update");
    require((state==SourceState::Complete?reason.empty():identifier(reason)) &&
        (platform.empty() || json::decimal_u64(platform)),"capture_invalid_reason");
    const auto at=slot(key.source);if(!matches(at,key) || key.capture!=state_.capture)return false;
    State next=state_;
    try {stage(next,at,key,graph,state,reason,platform,false);}
    catch(const std::invalid_argument&) {return update_failure(key,SourceState::Malformed,"provider_result_invalid");}
    catch(const json::Error&) {return update_failure(key,SourceState::Malformed,"provider_result_invalid");}
    const auto& before=state_.slots[at];const auto& after=next.slots[at];
    if(before.has_retained && before.retained_revision==after.retained_revision && before.visible.state==state &&
        before.visible.reason==reason && before.visible.platform==platform)return false;
    publish(std::move(next),at);return true;
}
bool ObservationCapture::update_failure(const CaptureKey& key,SourceState failure,const std::string& reason,const std::string& platform) {
    require(failure==SourceState::Denied || failure==SourceState::Malformed || failure==SourceState::Unavailable,"capture_invalid_failure");
    require(identifier(reason) && (platform.empty() || json::decimal_u64(platform)),"capture_invalid_reason");
    const auto at=slot(key.source);if(!matches(at,key) || key.capture!=state_.capture)return false;
    const auto& before=state_.slots[at].visible;
    if(before.state==failure && before.reason==reason && before.platform==platform)return false;
    State next=state_;auto& visible=next.slots[at].visible;visible.state=failure;visible.reason=reason;visible.platform=platform;
    publish(std::move(next),at);return true;
}
bool ObservationCapture::retired(const CaptureKey& key) {
    const auto at=slot(key.source);if(!matches(at,key))return false;State next=state_;
    if(!retire_old(next,at,key)) {
        auto& visible=next.slots[at].visible;visible.outstanding=false;
        if(visible.state==SourceState::Pending) {visible.state=SourceState::Unavailable;visible.reason="reader_exited_without_result";visible.platform.clear();}
    }
    publish(std::move(next),at);return true;
}
bool ObservationCapture::finish(const CaptureKey& key,const GraphInput& graph) {
    const auto at=slot(key.source);if(!matches(at,key))return false;State next=state_;
    if(retire_old(next,at,key)) {publish(std::move(next),at);return true;}
    // Invalid provider content is a source failure. Allocation failure is not
    // caught here: it leaves the outstanding attempt/prior snapshot unchanged.
    try {
        stage(next,at,key,graph,SourceState::Complete,"","",true);
    } catch(const std::invalid_argument&) {return fail(key,SourceState::Malformed,"provider_result_invalid");}
      catch(const json::Error&) {return fail(key,SourceState::Malformed,"provider_result_invalid");}
    publish(std::move(next),at);return true;
}
void ObservationCapture::next_capture() {
    State next=state_;increment(next.capture);
    next.capture_start=next.sequence;increment(next.capture_start);
    for(auto& item:next.slots) {
        item.visible.state=item.visible.outstanding?SourceState::Pending:SourceState::NotStarted;
        item.visible.reason=item.visible.outstanding?"previous_capture_outstanding":"";item.visible.platform.clear();
    }
    const auto reset=next.slots.size();publish(std::move(next),reset);
}
CaptureChanges ObservationCapture::changes(std::uint64_t capture,std::uint64_t after) const {
    require(after<=state_.sequence,"capture_future_cursor");CaptureChanges result;result.current=view_;
    result.resnapshot=capture!=state_.capture || after<state_.capture_start ||
        (!state_.notices.empty() && after<state_.notices.front().sequence-1);
    if(!result.resnapshot)for(const auto& notice:state_.notices)if(notice.sequence>after)result.notices.push_back(notice);
    return result;
}
}
