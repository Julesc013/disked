#include "storage_graph.h"
#include <type_traits>
#include <set>
namespace disked { namespace nt_inventory {
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
// Separately compiled injected-reader allocation probe, never a runtime option.
void storage_graph_publication_checkpoint(unsigned);
#endif
namespace {
using V=json::Value;
static_assert(std::is_nothrow_move_assignable<CaptureKey>::value && std::is_nothrow_move_assignable<StorageInput>::value,"binding prepared state must not allocate after registration");
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("storage_graph_shape");return *p;}
std::string text(const V& v,const char* k){const auto& x=get(v,k);if(x.kind!=V::Kind::string)throw std::invalid_argument("storage_graph_shape");return x.text;}
bool hex(const std::string& s,std::size_t n){return s.size()==n && s.find_first_not_of("0123456789abcdef")==std::string::npos;}
bool identity(const std::string& s,const char* prefix){const std::string p=prefix;return s.compare(0,p.size(),p)==0 && hex(s.substr(p.size()),32);}
}
V storage_graph_context(const V& observed,StorageFrameProfile profile){
    if(profile!=StorageFrameProfile::Metadata && profile!=StorageFrameProfile::IdentityLayout)throw std::invalid_argument("storage_graph_profile");
    const bool identity_profile=profile==StorageFrameProfile::IdentityLayout;
    if(text(observed,"schema")!=(identity_profile?"org.disked.nt-storage-worker-observation/2":"org.disked.nt-storage-worker-observation/1"))throw std::invalid_argument("storage_graph_context");auto out=V::object();
    for(const auto k:{"attempt_id","observer_epoch","worker_epoch","request_digest","code_sha256"})out.put(k,get(observed,k));
    const auto& worker=get(observed,"worker");out.put("pid",get(worker,"pid")).put("created",get(worker,"created"));
    if(!identity(text(out,"attempt_id"),identity_profile?"identity-attempt:":"storage-attempt:") || !identity(text(out,"observer_epoch"),"observer:") || !identity(text(out,"worker_epoch"),"worker:") || !hex(text(out,"request_digest"),64) || !hex(text(out,"code_sha256"),64) || !json::decimal_u64(text(out,"pid")) || text(out,"pid")=="0" || !json::decimal_u64(text(out,"created")) || text(out,"created")=="0")throw std::invalid_argument("storage_graph_context");
    if(identity_profile)out.put("storage_profile",V::string("identity-layout"));return out;
}
const V& StorageGraphEvidence::resolve(const std::string& kind,const std::string& digest)const{
    try{return current_->resolve(kind,digest);}catch(const std::invalid_argument&){
        if(last_complete_ && last_complete_!=current_)return last_complete_->resolve(kind,digest);throw;
    }
}
StorageGraphAdapter::StorageGraphAdapter(ObservationCapture& c,std::string s,StorageFrameProfile profile,StorageGraphProjection projection):
    capture_(c),source_(std::move(s)),profile_(profile),projection_(projection){
    if(capture_.snapshot()->graph.profile!=GraphProfile::Observations)throw std::invalid_argument("storage_graph_profile");
    if(profile!=StorageFrameProfile::Metadata && profile!=StorageFrameProfile::IdentityLayout)throw std::invalid_argument("storage_graph_profile");
    if((projection!=StorageGraphProjection::Frame && projection!=StorageGraphProjection::Identity) ||
        (projection==StorageGraphProjection::Identity && profile!=StorageFrameProfile::IdentityLayout))throw std::invalid_argument("storage_graph_projection");
}
void StorageGraphAdapter::start(const StorageQueryPolicy& policy,const V& fixture,const std::vector<StorageComparisonSelection>& comparisons){
    StorageInput input;input.capture_epoch=capture_.snapshot()->capture;input.policy=policy;input.provider_input=fixture;input.profile=profile_;validate_storage_input(input);
    if(comparisons.size()>16 || (!comparisons.empty() && (projection_!=StorageGraphProjection::Identity || !evidence_)))throw std::invalid_argument("storage_graph_comparisons");
    std::shared_ptr<const StorageIdentityProjection> previous;std::set<std::string> current_subjects;
    if(!comparisons.empty()){
        previous=evidence_->current();const auto& identity=previous->identity();const auto digest=storage_identity_digest(identity);
        if(identity.epoch_domain()!=capture_.epoch_domain())throw std::invalid_argument("storage_graph_comparison_domain");
        for(const auto& selection:comparisons){
            if(selection.previous_digest!=digest || selection.previous_subject.empty() || selection.current_subject.empty() ||
                selection.previous_subject.size()>64 || selection.current_subject.size()>64 || !current_subjects.insert(selection.current_subject).second)throw std::invalid_argument("storage_graph_comparison_selection");
            bool found=false;for(const auto& resource:get(identity.value(),"resources").items)if(text(resource,"subject")==selection.previous_subject && text(resource,"kind")=="disk")found=true;
            if(!found)throw std::invalid_argument("storage_graph_comparison_subject");
        }
    }
    auto prepared_comparisons=comparisons;
    if(session_ && text(get(session_->observe(),"worker"),"observation")!="exited" && !session_->never_launched())throw std::invalid_argument("storage_graph_reader_outstanding");
    std::uint64_t previous_worker=0;bool found=false;
    for(const auto& s:capture_.snapshot()->sources)if(s.id==source_){found=true;previous_worker=s.attempt.worker;if(s.outstanding)throw std::invalid_argument("storage_graph_reader_outstanding");}
    if(!found)throw std::invalid_argument("storage_graph_source");
    auto prepared=StorageWorker::prepare(input);CaptureKey registered{source_,input.capture_epoch,0,capture_.epoch_domain()};session_.swap(prepared);key_=std::move(registered);input_=std::move(input);context_=V{};
    comparisons_.swap(prepared_comparisons);comparison_previous_.swap(previous);
    try{auto key=capture_.start(source_);key_=std::move(key);session_->launch();context_=storage_graph_context(session_->observe(),profile_);}
    catch(...){
        if(!key_.worker)for(const auto& s:capture_.snapshot()->sources)if(s.id==source_ && s.outstanding && s.attempt.worker>previous_worker){key_.capture=s.attempt.capture;key_.worker=s.attempt.worker;}
        if(key_.worker){if(session_->never_launched())capture_.fail(key_,SourceState::Unavailable,"storage_start_never_launched");else capture_.update_failure(key_,SourceState::Unavailable,"storage_start_unresolved");}throw;
    }
}
void StorageGraphAdapter::release(){if(!session_)throw std::invalid_argument("storage_graph_not_started");session_->release();}
void StorageGraphAdapter::cancel(){if(!session_)throw std::invalid_argument("storage_graph_not_started");session_->cancel();}
bool StorageGraphAdapter::timeout(){return capture_.timeout(key_);}
bool StorageGraphAdapter::wait_entered(DWORD ms){if(!session_)throw std::invalid_argument("storage_graph_not_started");return session_->wait_entered(ms);}
void StorageGraphAdapter::consume(const V& observed){
    const auto state=text(get(observed,"worker"),"observation");if(state=="not_started"){capture_.fail(key_,SourceState::Unavailable,"storage_start_never_launched");return;}
    try{
        if(context_.kind==V::Kind::null)context_=storage_graph_context(observed,profile_);
        if(json::dump(storage_graph_context(observed,profile_))!=json::dump(context_) || text(observed,"capture_epoch")!=std::to_string(key_.capture))throw std::invalid_argument("storage_graph_binding");
        if(capture_.snapshot()->capture==key_.capture){
            const auto& result=get(observed,"result");
            if(result.kind==V::Kind::object){
                const auto frame=read_storage_frame(result,input_.provider_input,key_.capture,input_.policy,profile_);const auto status=text(result,"status");
                const bool complete=status=="selected_queries_complete";const auto context_digest=digest_sha256(json::dump(context_));
                GraphInput graph,prepared_complete;std::shared_ptr<const StorageGraphEvidence> prepared_evidence;
                if(projection_==StorageGraphProjection::Identity){
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
                    storage_graph_publication_checkpoint(1);
#endif
                    const auto owned=std::shared_ptr<const StorageFrameSnapshot>(new StorageFrameSnapshot(frame,key_,context_));
                    const IdentityBinding binding{key_,digest_sha256(json::dump(frame->value(),storage_observation_limits())),context_digest};
                    const auto identity=observe_storage_identity(*owned,binding);std::vector<IdentityComparisonBinding> selections;
                    for(const auto& s:comparisons_)selections.push_back({s.previous_digest,storage_identity_digest(*identity),s.previous_subject,s.current_subject});
                    const auto projection=project_storage_identity(owned,identity,binding,comparison_previous_,selections);
                    graph=projection->graph();const auto last_complete=complete?projection:(evidence_?evidence_->last_complete():nullptr);
                    if(!complete && last_complete){for(auto node:last_complete->graph().nodes){node.state="stale";graph.nodes.push_back(std::move(node));}
                        graph.edges.insert(graph.edges.end(),last_complete->graph().edges.begin(),last_complete->graph().edges.end());}
                    prepared_evidence=std::shared_ptr<const StorageGraphEvidence>(new StorageGraphEvidence(projection,last_complete));
                }else{
                    graph=project_storage_frame(*frame,key_,context_digest,context_);
                    if(!complete && have_previous_complete_){for(auto node:previous_complete_.nodes){node.state="stale";graph.nodes.push_back(std::move(node));}graph.edges.insert(graph.edges.end(),previous_complete_.edges.begin(),previous_complete_.edges.end());}
                    if(complete)prepared_complete=graph;
                }
                const auto expected=complete?SourceState::Complete:SourceState::Partial;
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
                storage_graph_publication_checkpoint(2);
#endif
                const bool changed=capture_.update(key_,graph,expected,complete?"":"storage_"+status);
                if(changed)for(const auto& source:capture_.snapshot()->sources)if(source.id==source_ && source.attempt==key_ && source.state==expected){
                    if(projection_==StorageGraphProjection::Identity)evidence_.swap(prepared_evidence);
                    else if(complete){previous_complete_.nodes.swap(prepared_complete.nodes);previous_complete_.edges.swap(prepared_complete.edges);previous_complete_.omissions.swap(prepared_complete.omissions);previous_complete_.profile=GraphProfile::Observations;have_previous_complete_=true;}
                }
            }else if(text(observed,"status")=="unknown")capture_.update_failure(key_,SourceState::Unavailable,"storage_worker_result_unknown");
        }
    }catch(const std::invalid_argument&){capture_.update_failure(key_,SourceState::Malformed,"storage_graph_result_invalid");}
     catch(const json::Error&){capture_.update_failure(key_,SourceState::Malformed,"storage_graph_result_invalid");}
    // Private consume receives only our owned session's actual handle result.
    if(state=="exited"){
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
        storage_graph_publication_checkpoint(3);
#endif
        capture_.retired(key_);comparison_previous_.reset();comparisons_.clear();
    }
}
V StorageGraphAdapter::poll(DWORD ms){if(!session_)throw std::invalid_argument("storage_graph_not_started");auto v=session_->observe(ms);consume(v);return v;}
V StorageGraphAdapter::retire(DWORD ms){if(!session_)throw std::invalid_argument("storage_graph_not_started");auto v=session_->retire(ms);consume(v);return v;}
std::shared_ptr<const StorageFrameSnapshot> StorageGraphAdapter::frame(){
    const auto observed=poll();const auto current=capture_.snapshot();if(current->capture!=key_.capture || text(observed,"status")!="completed")return {};
    bool accepted=false;for(const auto& source:current->sources)if(source.id==source_ && source.attempt==key_ &&
        (source.state==SourceState::Complete || source.state==SourceState::Partial))accepted=true;
    if(!accepted)return {};const auto context=storage_graph_context(observed,profile_);if(json::dump(context)!=json::dump(context_))throw std::invalid_argument("storage_graph_binding");
    if(projection_==StorageGraphProjection::Identity){
        if(!evidence_ || !(evidence_->current()->frame().key()==key_))return {};return evidence_->current()->frame_snapshot();
    }
    const auto result=read_storage_frame(get(observed,"result"),input_.provider_input,key_.capture,input_.policy,profile_);
    return std::shared_ptr<const StorageFrameSnapshot>(new StorageFrameSnapshot(result,key_,context));
}
}}
