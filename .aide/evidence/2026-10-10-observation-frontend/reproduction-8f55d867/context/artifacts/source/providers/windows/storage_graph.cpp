#include "storage_graph.h"
#include <type_traits>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
static_assert(std::is_nothrow_move_assignable<CaptureKey>::value && std::is_nothrow_move_assignable<StorageInput>::value,"binding prepared state must not allocate after registration");
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("storage_graph_shape");return *p;}
std::string text(const V& v,const char* k){const auto& x=get(v,k);if(x.kind!=V::Kind::string)throw std::invalid_argument("storage_graph_shape");return x.text;}
bool hex(const std::string& s,std::size_t n){return s.size()==n && s.find_first_not_of("0123456789abcdef")==std::string::npos;}
bool identity(const std::string& s,const char* prefix){const std::string p=prefix;return s.compare(0,p.size(),p)==0 && hex(s.substr(p.size()),32);}
}
V storage_graph_context(const V& observed){
    if(text(observed,"schema")!="org.disked.nt-storage-worker-observation/1")throw std::invalid_argument("storage_graph_context");auto out=V::object();
    for(const auto k:{"attempt_id","observer_epoch","worker_epoch","request_digest","code_sha256"})out.put(k,get(observed,k));
    const auto& worker=get(observed,"worker");out.put("pid",get(worker,"pid")).put("created",get(worker,"created"));
    if(!identity(text(out,"attempt_id"),"storage-attempt:") || !identity(text(out,"observer_epoch"),"observer:") || !identity(text(out,"worker_epoch"),"worker:") || !hex(text(out,"request_digest"),64) || !hex(text(out,"code_sha256"),64) || !json::decimal_u64(text(out,"pid")) || text(out,"pid")=="0" || !json::decimal_u64(text(out,"created")) || text(out,"created")=="0")throw std::invalid_argument("storage_graph_context");return out;
}
StorageGraphAdapter::StorageGraphAdapter(ObservationCapture& c,std::string s):capture_(c),source_(std::move(s)){
    if(capture_.snapshot()->graph.profile!=GraphProfile::Observations)throw std::invalid_argument("storage_graph_profile");
}
void StorageGraphAdapter::start(const StorageQueryPolicy& policy,const V& fixture){
    StorageInput input;input.capture_epoch=capture_.snapshot()->capture;input.policy=policy;input.provider_input=fixture;validate_storage_input(input);
    if(session_ && text(get(session_->observe(),"worker"),"observation")!="exited" && !session_->never_launched())throw std::invalid_argument("storage_graph_reader_outstanding");
    std::uint64_t previous_worker=0;bool found=false;
    for(const auto& s:capture_.snapshot()->sources)if(s.id==source_){found=true;previous_worker=s.attempt.worker;if(s.outstanding)throw std::invalid_argument("storage_graph_reader_outstanding");}
    if(!found)throw std::invalid_argument("storage_graph_source");
    auto prepared=StorageWorker::prepare(input);CaptureKey registered{source_,input.capture_epoch,0};session_.swap(prepared);key_=std::move(registered);input_=std::move(input);context_=V{};
    try{auto key=capture_.start(source_);key_=std::move(key);session_->launch();context_=storage_graph_context(session_->observe());}
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
        if(context_.kind==V::Kind::null)context_=storage_graph_context(observed);
        if(json::dump(storage_graph_context(observed))!=json::dump(context_) || text(observed,"capture_epoch")!=std::to_string(key_.capture))throw std::invalid_argument("storage_graph_binding");
        if(capture_.snapshot()->capture==key_.capture){
            const auto& result=get(observed,"result");
            if(result.kind==V::Kind::object){
                const auto frame=read_storage_frame(result,input_.provider_input,key_.capture,input_.policy);const auto status=text(result,"status");
                auto graph=project_storage_frame(*frame,key_,digest_sha256(json::dump(context_)),context_);
                if(status!="selected_queries_complete" && have_previous_complete_){for(auto node:previous_complete_.nodes){node.state="stale";graph.nodes.push_back(std::move(node));}graph.edges.insert(graph.edges.end(),previous_complete_.edges.begin(),previous_complete_.edges.end());}
                GraphInput prepared_complete;if(status=="selected_queries_complete")prepared_complete=graph;
                capture_.update(key_,graph,status=="selected_queries_complete"?SourceState::Complete:SourceState::Partial,status=="selected_queries_complete"?"":"storage_"+status);
                if(status=="selected_queries_complete")for(const auto& source:capture_.snapshot()->sources)if(source.id==source_ && source.state==SourceState::Complete){
                    previous_complete_.nodes.swap(prepared_complete.nodes);previous_complete_.edges.swap(prepared_complete.edges);previous_complete_.omissions.swap(prepared_complete.omissions);previous_complete_.profile=GraphProfile::Observations;have_previous_complete_=true;
                }
            }else if(text(observed,"status")=="unknown")capture_.update_failure(key_,SourceState::Unavailable,"storage_worker_result_unknown");
        }
    }catch(const std::invalid_argument&){capture_.update_failure(key_,SourceState::Malformed,"storage_graph_result_invalid");}
     catch(const json::Error&){capture_.update_failure(key_,SourceState::Malformed,"storage_graph_result_invalid");}
    // Private consume receives only our owned session's actual handle result.
    if(state=="exited")capture_.retired(key_);
}
V StorageGraphAdapter::poll(DWORD ms){if(!session_)throw std::invalid_argument("storage_graph_not_started");auto v=session_->observe(ms);consume(v);return v;}
V StorageGraphAdapter::retire(DWORD ms){if(!session_)throw std::invalid_argument("storage_graph_not_started");auto v=session_->retire(ms);consume(v);return v;}
}}
