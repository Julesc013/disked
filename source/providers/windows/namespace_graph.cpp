#include "namespace_graph.h"
#include <set>
#include <type_traits>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
static_assert(std::is_nothrow_move_assignable<CaptureKey>::value,"capture-key binding must not allocate after registration");
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw std::invalid_argument("namespace_graph_shape");return *p;}
std::string text(const V& v,const char* name) {const auto& p=field(v,name);if(p.kind!=V::Kind::string)throw std::invalid_argument("namespace_graph_shape");return p.text;}
bool hex(const std::string& s,std::size_t length) {return s.size()==length && s.find_first_not_of("0123456789abcdef")==std::string::npos;}
bool identity(const std::string& s,const char* prefix) {const std::string p=prefix;return s.compare(0,p.size(),p)==0 && hex(s.substr(p.size()),32);}
void validate_context(const V& context) {
    const std::set<std::string> fields={"attempt_id","observer_epoch","worker_epoch","request_digest","code_sha256","pid","created"};
    if(context.kind!=V::Kind::object || context.fields.size()!=fields.size())throw std::invalid_argument("namespace_graph_context");
    for(const auto& k:fields)text(context,k.c_str());
    if(!identity(text(context,"attempt_id"),"namespace-attempt:") || !identity(text(context,"observer_epoch"),"observer:") ||
        !identity(text(context,"worker_epoch"),"worker:") || !hex(text(context,"request_digest"),64) || !hex(text(context,"code_sha256"),64) ||
        !json::decimal_u64(text(context,"pid")) || text(context,"pid")=="0" || !json::decimal_u64(text(context,"created")) || text(context,"created")=="0")throw std::invalid_argument("namespace_graph_context");
}
GraphNode node(const V& snapshot,const NamespaceGraphBinding& b,const V& payload,const char* kind,const V& name) {
    GraphNode n;n.kind=kind;n.scope=GraphNodeScope::Observation;n.state="unknown";n.label=text(name,"display");
    n.observation.source=b.key.source;n.observation.capture=b.key.capture;n.observation.worker=b.key.worker;
    n.observation.context_digest=digest_sha256(json::dump(b.worker_context));n.observation.frame_digest=digest_sha256(json::dump(snapshot,volume_inventory_limits()));
    n.observation.payload=payload;n.id=observation_node_id(n);return n;
}
}
V namespace_graph_context(const V& observed) {
    if(text(observed,"schema")!="org.disked.nt-namespace-worker-observation/1")throw std::invalid_argument("namespace_graph_context");
    auto v=V::object();for(const auto k:{"attempt_id","observer_epoch","worker_epoch","request_digest","code_sha256"})v.put(k,field(observed,k));
    const auto& worker=field(observed,"worker");v.put("pid",field(worker,"pid")).put("created",field(worker,"created"));validate_context(v);return v;
}
GraphInput project_namespace_snapshot(const V& snapshot,const NamespaceGraphBinding& b) {
    validate_context(b.worker_context);validate_namespace_snapshot(snapshot,b.key.capture,b.policy);
    if(!b.key.worker)throw std::invalid_argument("namespace_graph_binding");GraphInput graph;graph.profile=GraphProfile::Observations;
    std::size_t ordinal=0;
    for(const auto& row:field(snapshot,"records").items) {
        ++ordinal;const auto& mounts=field(row,"mounts");
        auto base=V::object().put("provider_observation_id",field(row,"observation_id")).put("volume_ordinal",V::string(std::to_string(ordinal)))
            .put("record_state",field(row,"state")).put("conflicts",field(row,"conflicts")).put("mount_state",field(mounts,"state"))
            .put("mount_platform_code",field(mounts,"platform_code")).put("worker_context",b.worker_context);
        auto volume=base;volume.put("name",field(row,"volume_path")).put("mount_ordinal",V::string("0"));
        auto v=node(snapshot,b,volume,"namespace-volume-observation",field(row,"volume_path"));const auto parent=v.id;graph.nodes.push_back(std::move(v));
        std::size_t mount=0;
        for(const auto& path:field(mounts,"paths").items) {
            auto data=base;data.put("name",path).put("mount_ordinal",V::string(std::to_string(++mount))).put("parent_observation",V::string(parent));
            auto child=node(snapshot,b,data,"namespace-mount-observation",path);graph.edges.push_back({parent,child.id,"mounts"});graph.nodes.push_back(std::move(child));
        }
    }
    if(text(snapshot,"status")!="complete")graph.omissions.push_back("namespace:"+text(snapshot,"status")+":"+text(field(snapshot,"enumeration"),"state"));
    GraphSnapshot::create(graph,b.key.capture);return graph;
}
NamespaceGraphAdapter::NamespaceGraphAdapter(ObservationCapture& capture,std::string source):capture_(capture),source_(std::move(source)) {
    if(capture_.snapshot()->graph.profile!=GraphProfile::Observations)throw std::invalid_argument("namespace_graph_profile");
}
void NamespaceGraphAdapter::start(const InventoryPolicy& policy,const V& fixture) {
    NamespaceInput input;input.capture_epoch=capture_.snapshot()->capture;input.policy=policy;input.provider_input=fixture;validate_namespace_input(input);
    if(session_ && text(field(session_->observe(),"worker"),"observation")!="exited" && !session_->never_launched())throw std::invalid_argument("namespace_graph_reader_outstanding");
    std::uint64_t previous_worker=0;bool found=false;
    for(const auto& s:capture_.snapshot()->sources)if(s.id==source_) {found=true;previous_worker=s.attempt.worker;if(s.outstanding)throw std::invalid_argument("namespace_graph_reader_outstanding");}
    if(!found)throw std::invalid_argument("namespace_graph_source");
    auto prepared=NamespaceWorker::prepare(input);CaptureKey registered{source_,input.capture_epoch,0};
    session_.swap(prepared);key_=std::move(registered);policy_=policy;context_=V{};
    // Ownership is retained before launch; a post-spawn exception cannot lose
    // the exact process handle. No-launch and unresolved launch are distinct.
    try {auto key=capture_.start(source_);key_=std::move(key);session_->launch();context_=namespace_graph_context(session_->observe());}
    catch(...) {
        // If returning the registered key threw, recover its scalar epochs
        // without allocating; the retained prepared session proves no launch.
        if(!key_.worker)for(const auto& s:capture_.snapshot()->sources)if(s.id==source_ && s.outstanding && s.attempt.worker>previous_worker) {key_.capture=s.attempt.capture;key_.worker=s.attempt.worker;}
        if(key_.worker) {if(session_->never_launched())capture_.fail(key_,SourceState::Unavailable,"namespace_start_never_launched");else capture_.update_failure(key_,SourceState::Unavailable,"namespace_start_unresolved");}throw;
    }
}
void NamespaceGraphAdapter::release() {if(!session_)throw std::invalid_argument("namespace_graph_not_started");session_->release();}
void NamespaceGraphAdapter::cancel() {if(!session_)throw std::invalid_argument("namespace_graph_not_started");session_->cancel();}
bool NamespaceGraphAdapter::timeout() {return capture_.timeout(key_);}
bool NamespaceGraphAdapter::wait_entered(DWORD ms) {if(!session_)throw std::invalid_argument("namespace_graph_not_started");return session_->wait_entered(ms);}
void NamespaceGraphAdapter::consume(const V& observed) {
    const auto worker_state=text(field(observed,"worker"),"observation");
    if(worker_state=="not_started") {capture_.fail(key_,SourceState::Unavailable,"namespace_start_never_launched");return;}
    try {
        if(context_.kind==V::Kind::null)context_=namespace_graph_context(observed);
        if(json::dump(namespace_graph_context(observed))!=json::dump(context_) || text(observed,"capture_epoch")!=std::to_string(key_.capture))throw std::invalid_argument("namespace_graph_binding");
    }catch(const std::invalid_argument&) {
        capture_.update_failure(key_,SourceState::Unavailable,"namespace_context_unavailable");
        if(worker_state=="exited")capture_.retired(key_);return;
    }
    const auto& result=field(observed,"result");
    if(capture_.snapshot()->capture==key_.capture) {
      try {
        if(result.kind==V::Kind::object) {
            const auto status=text(result,"status");
            if(status=="complete" || status=="partial" || status=="cancelled") {
                auto graph=project_namespace_snapshot(result,{key_,context_,policy_});
                if(status!="complete" && have_previous_complete_) {
                    for(auto node:previous_complete_.nodes) {node.state="stale";graph.nodes.push_back(std::move(node));}
                    graph.edges.insert(graph.edges.end(),previous_complete_.edges.begin(),previous_complete_.edges.end());
                }
                GraphInput prepared_complete;if(status=="complete")prepared_complete=graph;
                capture_.update(key_,graph,status=="complete"?SourceState::Complete:SourceState::Partial,status=="complete"?"":"namespace_"+status);
                const auto& sources=capture_.snapshot()->sources;
                for(const auto& source:sources)if(status=="complete" && source.id==source_ && source.state==SourceState::Complete) {
                    // Prepare retained complete content before accepting another
                    // capture. Partial frames never recursively grow this cache.
                    previous_complete_.nodes.swap(prepared_complete.nodes);previous_complete_.edges.swap(prepared_complete.edges);
                    previous_complete_.omissions.swap(prepared_complete.omissions);previous_complete_.profile=GraphProfile::Observations;have_previous_complete_=true;
                }
            } else capture_.update_failure(key_,status=="denied"?SourceState::Denied:SourceState::Unavailable,"namespace_"+status,text(field(result,"enumeration"),"platform_code"));
        } else if(text(observed,"status")=="unknown")capture_.update_failure(key_,SourceState::Unavailable,"namespace_worker_result_unknown");
      } catch(const std::invalid_argument&) {capture_.update_failure(key_,SourceState::Malformed,"namespace_graph_result_invalid");}
        catch(const json::Error&) {capture_.update_failure(key_,SourceState::Malformed,"namespace_graph_result_invalid");}
    }
    // Only the owned session's exact process-handle exit retires the attempt.
    if(text(field(observed,"worker"),"observation")=="exited")capture_.retired(key_);
}
V NamespaceGraphAdapter::poll(DWORD ms) {if(!session_)throw std::invalid_argument("namespace_graph_not_started");auto v=session_->observe(ms);consume(v);return v;}
V NamespaceGraphAdapter::retire(DWORD ms) {if(!session_)throw std::invalid_argument("namespace_graph_not_started");auto v=session_->retire(ms);consume(v);return v;}
}}
