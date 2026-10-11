#include "storage_graph.h"
#include "namespace_graph.h"
#include "storage_fixture.h"
#include "volume_fixture.h"
#include "session.h"
#include "gui_model.h"
#include "shell_model.h"
#include "tui_model.h"
#include "cli.h"
#include "memory_budget.h"
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
#include "inventory_session.h"
#endif
#include <algorithm>
#if defined(DISKED_NT_IDENTITY_PROJECTION_TESTING)
#include "storage_identity.h"
#endif
#include <cstdio>
#include <cstdlib>
#include <new>
#include <io.h>
#include <fcntl.h>

// Selected controller-only publication allocation failure, not an allocator
// replacement, exhaustiveness claim or a worker/storage failure.
namespace {bool fail_next_allocation=false;}
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
namespace {bool fail_inventory_publication=false;unsigned inventory_allocation_hits=0;}
namespace disked {namespace nt_inventory {
void inventory_publication_checkpoint(){if(fail_inventory_publication){fail_inventory_publication=false;++inventory_allocation_hits;fail_next_allocation=true;}}
}}
#endif
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
namespace {unsigned allocation_checkpoint=0,allocation_checkpoint_hits=0;}
namespace disked {namespace nt_inventory {
void storage_graph_publication_checkpoint(unsigned point){
    if(allocation_checkpoint==point){allocation_checkpoint=0;++allocation_checkpoint_hits;fail_next_allocation=true;}
}
}}
#endif
void* operator new(std::size_t n) {if(fail_next_allocation){fail_next_allocation=false;throw std::bad_alloc();}if(auto p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n) {return ::operator new(n);}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete[](void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
void operator delete[](void* p,std::size_t) noexcept {std::free(p);}

namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
#if defined(DISKED_NT_IDENTITY_FRONTEND_TESTING)
const auto storage_profile=n::StorageFrameProfile::IdentityLayout;
#else
const auto storage_profile=n::StorageFrameProfile::Metadata;
#endif
const V& get(const V& v,const char* k) {auto p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::string text(const V& v,const char* k) {const auto& x=get(v,k);if(x.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return x.text;}
std::uint32_t count(const V& v,const char* k,std::uint32_t max) {const auto s=text(v,k);if(!disked::json::decimal_u64(s))throw std::invalid_argument("fixture_count");auto x=std::stoull(s);if(x>max)throw std::invalid_argument("fixture_count");return static_cast<std::uint32_t>(x);}
void require(bool ok,const char* why) {if(!ok)throw std::runtime_error(why);}
void print(const V& v) {disked::json::Limits l;l.bytes=33554432;l.values=1048576;l.depth=40;l.string_bytes=8388608;std::puts(disked::json::dump(v,l).c_str());std::fflush(stdout);}
V lines(const std::vector<std::string>& rows) {auto v=V::array();for(const auto& s:rows)v.items.push_back(V::string(s));return v;}
std::string joined(const std::vector<std::string>& rows) {std::string v;for(const auto& s:rows){v+=s;v+='\n';}return v;}
V compact_state(V v) {v.fields.erase("last_outcome");v.fields.erase("transcript");v.fields.erase("earlier_request");return v;}
void key(disked::TuiModel& m,disked::TextKey k) {m.input({k,"",false});}
void key(disked::ShellModel& m,disked::TextKey k) {m.input({k,"",false});}
void submit(disked::ShellModel& m,const std::string& s) {m.input({disked::TextKey::Text,s,false});key(m,disked::TextKey::F9);key(m,disked::TextKey::F9);}
V cli_view(const disked::Outcome& outcome,const std::string& command,const disked::Registry& registry) {
    disked::ParseResult parsed;parsed.command_id=command;disked::InvocationHost host;host.output_usable=host.error_usable=true;
    const auto normal=disked::cli_text(outcome,parsed,host,registry,false,false),background=disked::cli_text(outcome,parsed,host,registry,true,false);
    host.output_usable=false;const auto unavailable=disked::cli_text(outcome,parsed,host,registry,false,false);
    return V::object().put("available",V::boolean_value(normal.available)).put("diagnostic",V::boolean_value(normal.diagnostic))
        .put("human",V::string(normal.bytes)).put("background",V::string(background.bytes)).put("unavailable",V::boolean_value(unavailable.available));
}
#if defined(DISKED_NT_IDENTITY_FRONTEND_TESTING)
V inspect_session(disked::FrontendSession& session,const disked::Registry& registry,const V& discovery,const char* source) {
    const auto snapshot=session.snapshot();auto out=V::array();const auto& nodes=get(snapshot->value(),"nodes").items;
    for(std::size_t i=0;i<nodes.size();++i) {
        const auto& properties=get(nodes[i],"properties");if(text(properties,"scope")!="observation-only" || text(get(properties,"observation_binding"),"source")!=source)continue;
        const auto id=text(nodes[i],"id");auto dispatch=[&](const std::string& r,const std::string& c,const V& p,const std::string& revision){return session.dispatch(r,c,p,revision);};
        const auto direct=session.dispatch("all:direct","target.inspect",V::object().put("target_id",V::string(id)));
        disked::GuiModel gui(session,registry,discovery,dispatch);gui.focus(id);gui.open();
        disked::TuiModel tui(session,registry,discovery,dispatch);for(std::size_t j=0;j<i;++j)key(tui,disked::TextKey::Down);key(tui,disked::TextKey::Enter);
        disked::ShellModel shell(session,registry,discovery,dispatch,false);submit(shell,"target inspect "+id);
        auto digest=[](const V& v) {return V::string(disked::digest_sha256(disked::json::dump(v,disked::cached_observation_view_limits())));};
        auto display_limits=disked::cached_observation_view_limits();display_limits.bytes=8388608;display_limits.depth=35;
        const auto cli=cli_view(direct,"target.inspect",registry);const auto gr=get(gui.state(),"last_outcome"),tr=get(tui.state(),"last_outcome"),sr=get(shell.state(),"last_outcome");
        const auto gd=disked::json::parse(gui.detail_text(),display_limits);const auto rendered=tui.render(80,25,true);std::string body;
        require(rendered.size()>=6,"fixture_tui_display");for(std::size_t j=3;j+3<rendered.size();++j){body+=rendered[j];body+='\n';}
        const auto td=disked::json::parse(body,display_limits);
        const auto health=session.dispatch("all:health","health.assess",V::object().put("target_id",V::string(id)));
        const auto cap=session.dispatch("all:capability","capability.explain",V::object().put("target_id",V::string(id)).put("operation",V::string("health.assess")));
        const auto& assessment=get(get(cap.response,"result"),"assessment");
        auto row=V::object().put("id",V::string(id)).put("direct",direct.response)
            .put("gui",digest(get(gr,"result"))).put("tui",digest(get(tr,"result"))).put("shell",digest(get(sr,"result")))
            .put("cli_human",digest(disked::json::parse(text(cli,"human"),display_limits))).put("cli_background",digest(disked::json::parse(text(cli,"background"),display_limits)))
            .put("gui_display",digest(get(gd,"result"))).put("tui_display",digest(get(td,"result")))
            .put("health_refused",V::boolean_value(text(health.response,"status")=="refused" && text(get(health.response,"diagnostics").items.at(0),"code")=="observation_not_storage_target"))
            .put("capability_unqualified",V::boolean_value(!get(assessment,"execution_eligible").boolean && !get(assessment,"authorizes_execution").boolean && get(assessment,"target_id").kind==V::Kind::null && text(assessment,"observation_id")==id));
        out.items.push_back(std::move(row));
    }
    return out;
}
V inspect_storage(const disked::GraphInput& graph,const disked::Registry& registry,const V& discovery) {
    unsigned calls=0;disked::FrontendSession session(registry,graph,{},[&](const std::string& id,const V&,const std::string&,const V&){++calls;return disked::completed(id,V::object());},disked::FrontendProfile::CachedObservations);
    const auto result=inspect_session(session,registry,discovery,"storage");require(!calls,"fixture_storage_health_called");return result;
}
V storage_focus(const disked::GraphInput& original,const disked::GraphInput& current,const disked::Registry& registry,const char* preferred="storage-partition-observation",const char* source="storage") {
    std::string id;for(const auto& node:original.nodes)if(node.scope==disked::GraphNodeScope::Observation && node.observation.source==source) {
        if(id.empty() || node.kind==preferred)id=node.id;if(node.kind==preferred)break;
    }
    if(id.empty())return V{};
    disked::FrontendSession session(registry,original,{},{},disked::FrontendProfile::CachedObservations);const auto before=session.snapshot();
    session.act({disked::ActionKind::Select,id,before->revision(),"focus:select"});session.publish(current);
    const auto after=session.snapshot();const auto stale=session.dispatch("focus:stale","target.inspect",V::object().put("target_id",V::string(id)),before->revision());
    const auto inspected=session.dispatch("focus:current","target.inspect",V::object().put("target_id",V::string(id)),after->revision());
    return V::object().put("old_id",V::string(id)).put("selection",session.selection()).put("stale",stale.response).put("inspection",inspected.response)
        .put("present",V::boolean_value(after->node(id)!=nullptr));
}
#endif
disked::GraphInput synthetic(const V& input) {
    disked::GraphInput g;g.profile=disked::GraphProfile::Observations;
    const auto size=count(input,"count",321),fill=count(input,"fill",4096),extra=count(input,"extra",319);
    for(std::uint32_t i=0;i<size;++i) {
        disked::GraphNode node;node.kind="synthetic-observation";node.scope=disked::GraphNodeScope::Observation;node.state="unknown";node.label=std::string(512,'L');
        auto& o=node.observation;o.source="synthetic-render";o.capture=1;o.worker=1;o.context_digest="sha256:"+std::string(64,'0');o.frame_digest="sha256:"+std::string(64,'1');
        auto parts=V::array();for(unsigned j=0;j<24;++j)parts.items.push_back(V::string("x"));
        o.payload=V::object().put("synthetic",V::boolean_value(true)).put("ordinal",V::string(std::to_string(i))).put("parts",parts).put("text",V::string(std::string(fill+(i<extra?1:0),'x')));
        node.id=disked::observation_node_id(node);g.nodes.push_back(std::move(node));
    }
    return g;
}
template<class Adapter,class Policy>
V owned(Adapter& a,const Policy& p,const V& fixture) {
    a.start(p,fixture);auto before=a.poll();a.release();V result;
    const auto end=GetTickCount64()+3000;
    do {result=a.poll(1000);if(text(get(result,"worker"),"observation")=="exited")break;}while(GetTickCount64()<end);
    require(text(get(result,"worker"),"observation")=="exited","fixture_reader_not_retired");
    return V::object().put("before",before).put("after",result);
}
#if defined(DISKED_NT_IDENTITY_PROJECTION_TESTING)
V identity_projection(const V& input,const disked::WindowsMemoryBudget& budget){
    const auto& reg=get(input,"registry");disked::Registry registry{get(reg,"commands"),get(reg,"syntax"),get(reg,"schemas")};
    auto commands=registry.commands;for(auto& command:commands.items)command.put("availability",V::string(disked::FrontendSession::handles(text(command,"id"))?"available":"unavailable"));
    auto discovery=V::object().put("commands",commands);const auto& stages=get(input,"stages");
    if(stages.kind!=V::Kind::array || stages.items.empty() || stages.items.size()>3)throw std::invalid_argument("fixture_stages");
    const auto fault=input.find("fault")?text(input,"fault"):"";
    const std::vector<std::string> faults={"","source","capture","worker","frame_digest","context_digest","domain_missing","domain_foreign","identity_mismatch","identity_null","frame_null","comparison_digest","comparison_subject","comparison_duplicate","comparison_limit","previous_unused","previous_absent","allocation"};
    require(std::find(faults.begin(),faults.end(),fault)!=faults.end(),"fixture_fault");
    auto capture=std::unique_ptr<disked::ObservationCapture>(new disked::ObservationCapture({"storage"},disked::GraphProfile::Observations));
    auto adapter=std::unique_ptr<n::StorageGraphAdapter>(new n::StorageGraphAdapter(*capture,"storage",n::StorageFrameProfile::IdentityLayout));
    std::shared_ptr<const n::StorageIdentityProjection> previous,last_complete;disked::GraphInput previous_graph;std::string first_frame_digest;auto rows=V::array();bool refused=false;
    for(std::size_t index=0;index<stages.items.size();++index){
        const auto& stage=stages.items[index];if(index){
            if(stage.find("new_domain") && get(stage,"new_domain").boolean){adapter.reset();capture.reset(new disked::ObservationCapture({"storage"},disked::GraphProfile::Observations));adapter.reset(new n::StorageGraphAdapter(*capture,"storage",n::StorageFrameProfile::IdentityLayout));}
            else capture->next_capture();
        }
        const auto previous_digest=previous?n::storage_identity_digest(previous->identity()):"";
        const bool live=stage.find("live") && get(stage,"live").boolean;auto row=V::object();
        if(live){adapter->start(n::StorageQueryPolicy{},get(stage,"fixture"));const auto started=adapter->poll();adapter->release();V observed;const auto deadline=GetTickCount64()+1000;
            do{observed=adapter->poll(1);if(text(observed,"status")=="completed")break;}while(GetTickCount64()<deadline);
            require(text(observed,"status")=="completed" && text(get(observed,"worker"),"observation")=="running","fixture_live_frame_missing");
            row.put("worker",V::object().put("before",started).put("after",observed));
        }else row.put("worker",owned(*adapter,n::StorageQueryPolicy{},get(stage,"fixture")));
        const auto frame=adapter->frame();
        require(bool(frame),"fixture_frame_missing");const auto frame_digest=disked::digest_sha256(disked::json::dump(frame->frame().value(),n::storage_observation_limits()));
        n::IdentityBinding binding{frame->key(),frame_digest,disked::digest_sha256(disked::json::dump(frame->context()))};
        const auto identity=n::observe_storage_identity(*frame,binding);auto selected_frame=frame;auto selected_identity=identity;
        std::vector<n::IdentityComparisonBinding> comparisons;
        if(previous)comparisons.push_back({n::storage_identity_digest(previous->identity()),n::storage_identity_digest(*identity),"disk","disk"});
        if(const auto* declarations=stage.find("comparisons")){comparisons.clear();if(declarations->kind!=V::Kind::array)throw std::invalid_argument("fixture_comparisons");
            for(const auto& d:declarations->items)comparisons.push_back({previous?n::storage_identity_digest(previous->identity()):"",n::storage_identity_digest(*identity),text(d,"previous_subject"),text(d,"current_subject")});}
        auto selected_previous=previous;
        if(index+1==stages.items.size()){
            if(fault=="source")binding.capture.source="foreign";
            if(fault=="capture")++binding.capture.capture;if(fault=="worker")++binding.capture.worker;
            if(fault=="frame_digest")binding.frame_digest="sha256:"+std::string(64,'0');if(fault=="context_digest")binding.context_digest="sha256:"+std::string(64,'0');
            if(fault=="domain_missing")binding.capture.domain.reset();
            if(fault=="domain_foreign"){disked::ObservationCapture foreign({"storage"},disked::GraphProfile::Observations);binding.capture.domain=foreign.epoch_domain();}
            if(fault=="identity_mismatch"){require(bool(previous),"fixture_previous_missing");selected_identity=std::make_shared<const n::StorageIdentityObservation>(previous->identity());}
            if(fault=="identity_null")selected_identity.reset();if(fault=="frame_null")selected_frame.reset();
            if(fault=="previous_unused")comparisons.clear();if(fault=="previous_absent")selected_previous.reset();
            if(fault=="comparison_digest"){require(!comparisons.empty(),"fixture_comparison_missing");comparisons[0].previous_digest="sha256:"+std::string(64,'0');}
            if(fault=="comparison_subject"){require(!comparisons.empty(),"fixture_comparison_missing");comparisons[0].current_subject="missing";}
            if(fault=="comparison_duplicate"){require(!comparisons.empty(),"fixture_comparison_missing");comparisons.push_back(comparisons[0]);}
            if(fault=="comparison_limit"){require(!comparisons.empty(),"fixture_comparison_missing");while(comparisons.size()<17)comparisons.push_back(comparisons[0]);}
        }
        row.put("frame",frame->frame().value()).put("identity",identity->value()).put("context",frame->context());
        const auto before=capture->snapshot();std::shared_ptr<const n::StorageIdentityProjection> projected;
        try{
            if(fault=="allocation" && index+1==stages.items.size())fail_next_allocation=true;
            projected=n::project_storage_identity(selected_frame,selected_identity,binding,selected_previous,comparisons);
        }catch(const std::exception& e){fail_next_allocation=false;row.put("error",V::string(e.what()));refused=true;}
        fail_next_allocation=false;require(before==capture->snapshot(),"fixture_projection_changed_capture");
        row.put("capture_unchanged",V::boolean_value(true)).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
        if(!projected){row.put("previous_preserved",V::boolean_value(!previous || n::storage_identity_digest(previous->identity())==previous_digest));rows.items.push_back(std::move(row));continue;}
        const auto status=text(frame->frame().value(),"status");if(status=="selected_queries_complete")last_complete.reset();
        std::weak_ptr<const n::StorageIdentityProjection> old=previous;previous.reset();selected_previous.reset();
        const bool retained_for_cache=!old.expired() && last_complete==old.lock();require(old.expired() || retained_for_cache,"fixture_projection_history_chain");
        auto graph=projected->graph();
        if(last_complete){
            for(auto node:last_complete->graph().nodes){node.state="stale";graph.nodes.push_back(std::move(node));}
            graph.edges.insert(graph.edges.end(),last_complete->graph().edges.begin(),last_complete->graph().edges.end());
        }
        auto resolved=V::array(),artifacts=V::object();for(const auto& node:graph.nodes)if(node.kind=="storage-identity-observation"){
            const auto& references=get(node.observation.payload,"references");for(const auto& entry:references.fields){
                const V* value=nullptr;std::string resolver="current-projection";
                try{value=&projected->resolve(text(entry.second,"kind"),text(entry.second,"digest"));}catch(const std::invalid_argument&){
                    if(!last_complete)throw;value=&last_complete->resolve(text(entry.second,"kind"),text(entry.second,"digest"));resolver="last-complete-projection";}
                const auto artifact=text(entry.second,"kind")+":"+text(entry.second,"digest");if(!artifacts.find(artifact))artifacts.put(artifact,*value);
                resolved.items.push_back(V::object().put("node",V::string(node.id)).put("name",V::string(entry.first)).put("reference",entry.second).put("artifact",V::string(artifact)).put("resolver",V::string(resolver)));}
        }
        bool unknown_kind=false,unknown_digest=false;try{projected->resolve("../file",frame_digest);}catch(const std::invalid_argument&){unknown_kind=true;}
        try{projected->resolve("frame","sha256:"+std::string(64,'0'));}catch(const std::invalid_argument&){unknown_digest=true;}
        bool pruned=true;if(index>1)try{projected->resolve("frame",first_frame_digest);pruned=false;}catch(const std::invalid_argument&){}
        const auto snapshot=disked::GraphSnapshot::create(graph,frame->key().capture);
        disked::FrontendSession guarded(registry,graph,{},{},disked::FrontendProfile::CachedObservations);const auto guarded_snapshot=guarded.snapshot();
        const auto focus_id=graph.nodes.back().id;guarded.act({disked::ActionKind::Select,focus_id,guarded_snapshot->revision(),"guard:select"});const auto guarded_selection=disked::json::dump(guarded.selection());
        auto oversized_graph=graph;oversized_graph.nodes.resize(321,graph.nodes.front());std::string graph_refusal;
        try{guarded.publish(oversized_graph);}catch(const std::invalid_argument& e){graph_refusal=e.what();}
        require(graph_refusal=="graph_limit" && guarded.snapshot()==guarded_snapshot && disked::json::dump(guarded.selection())==guarded_selection,"fixture_graph_not_atomic");
        bool allocation_refused=false;fail_next_allocation=true;try{guarded.publish(graph);}catch(const std::bad_alloc&){allocation_refused=true;}fail_next_allocation=false;
        require(allocation_refused && guarded.snapshot()==guarded_snapshot && disked::json::dump(guarded.selection())==guarded_selection,"fixture_publication_not_atomic");
        bool domains=true;for(const auto& node:graph.nodes)domains=domains && node.observation.domain==frame->key().domain;
        row.put("graph",snapshot->value()).put("resolved",resolved).put("artifacts",artifacts).put("comparisons",projected->comparisons()).put("inspections",inspect_storage(graph,registry,discovery))
            .put("previous_object_expired",V::boolean_value(old.expired())).put("previous_retained_for_cache",V::boolean_value(retained_for_cache)).put("unknown_reference_refused",V::boolean_value(unknown_kind && unknown_digest)).put("oldest_reference_pruned",V::boolean_value(pruned))
            .put("domains_retained",V::boolean_value(domains)).put("frame_digest",V::string(frame_digest));
        row.put("graph_refusal",V::string(graph_refusal)).put("publication_allocation_refused",V::boolean_value(allocation_refused));
        if(index)row.put("focus",storage_focus(previous_graph,graph,registry,"storage-identity-observation"));
        row.put("base_graph",disked::GraphSnapshot::create(before->graph,frame->key().capture)->value());
        if(live){const auto live_worker=adapter->poll();const bool outstanding=capture->snapshot()->sources[0].outstanding;const auto retirement=adapter->retire();
            row.put("live_worker",live_worker).put("live_outstanding",V::boolean_value(outstanding)).put("retirement",retirement);}
        if(!index)first_frame_digest=frame_digest;
        if(status=="selected_queries_complete")last_complete=projected;
        previous_graph=projected->graph();previous=std::move(projected);rows.items.push_back(std::move(row));
    }
    return V::object().put("status",V::string(refused?"refused":"observed")).put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("stages",rows)
        .put("frontend_budget_ready",V::boolean_value(budget.ready())).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
}
#endif
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
V identity_adapter(const V& input,const disked::WindowsMemoryBudget& budget){
    const auto& reg=get(input,"registry");disked::Registry registry{get(reg,"commands"),get(reg,"syntax"),get(reg,"schemas")};
    auto commands=registry.commands;for(auto& command:commands.items)command.put("availability",V::string(disked::FrontendSession::handles(text(command,"id"))?"available":"unavailable"));
    const auto discovery=V::object().put("commands",commands);const auto& stages=get(input,"stages");
    require(stages.kind==V::Kind::array && !stages.items.empty() && stages.items.size()<=4,"fixture_stages");
    disked::ObservationCapture capture({"storage","peer"},disked::GraphProfile::Observations);
    auto adapter=std::unique_ptr<n::StorageGraphAdapter>(new n::StorageGraphAdapter(capture,"storage",n::StorageFrameProfile::IdentityLayout,n::StorageGraphProjection::Identity));
    disked::GraphInput previous_graph;auto rows=V::array();std::shared_ptr<const n::StorageGraphEvidence> retained;
    auto source=[&](){const auto& s=capture.snapshot()->sources[0];return V::object().put("state",V::string(disked::source_state_name(s.state)))
        .put("outstanding",V::boolean_value(s.outstanding)).put("capture",V::string(std::to_string(capture.snapshot()->capture))).put("sequence",V::string(std::to_string(capture.snapshot()->sequence)));};
    for(std::size_t index=0;index<stages.items.size();++index){
        if(index)capture.next_capture();const auto& stage=stages.items[index];const auto& fixture=get(stage,"fixture");
        auto old_evidence=adapter->evidence();const auto action=stage.find("action")?text(stage,"action"):"complete";
        std::vector<n::StorageComparisonSelection> selections;
        if(const auto* declared=stage.find("comparisons"))for(const auto& d:declared->items){
            const auto prior=d.find("previous_digest")?text(d,"previous_digest"):(old_evidence?n::storage_identity_digest(old_evidence->current()->identity()):"");
            selections.push_back({prior,text(d,"previous_subject"),text(d,"current_subject")});}
        if(action=="graph-pressure"){
            const auto peer=capture.start("peer");auto graph=synthetic(V::object().put("count",V::string("300")).put("fill",V::string("0")).put("extra",V::string("0")));
            for(auto& node:graph.nodes){auto& o=node.observation;o.source="peer";o.capture=peer.capture;o.worker=peer.worker;o.domain=peer.domain;node.id=disked::observation_node_id(node);}
            capture.finish(peer,graph);require(capture.snapshot()->sources[1].state==disked::SourceState::Complete,"fixture_peer_not_accepted");
        }
        auto row=V::object(),workers=V::array();bool started=true;const auto before_start=capture.snapshot();const auto before_key=adapter->key();
        try{adapter->start(n::StorageQueryPolicy{},fixture,selections);}catch(const std::invalid_argument& e){
            row.put("start_error",V::string(e.what())).put("refused_start_key_unchanged",V::boolean_value(adapter->key()==before_key))
                .put("refused_start_capture_unchanged",V::boolean_value(capture.snapshot()==before_start));started=false;
        }
        if(started){
            workers.items.push_back(adapter->poll());row.put("pending_source",source()).put("pending_evidence_preserved",V::boolean_value(adapter->evidence()==old_evidence));
            if(action=="cancel-before")adapter->cancel();adapter->release();
            if(action=="superseded" || action=="timeout" || action=="cancel-during" || action=="retire"){
                require(adapter->wait_entered(1000),"fixture_not_entered");
                if(action=="superseded")capture.next_capture();else adapter->timeout();
                row.put("waiting_source",source()).put("waiting_evidence_preserved",V::boolean_value(adapter->evidence()==old_evidence));
                if(action=="cancel-during")adapter->cancel();
            }
            if(stage.find("allocation_checkpoint"))allocation_checkpoint=count(stage,"allocation_checkpoint",3);
            const auto before=capture.snapshot();V observed;bool allocation_failed=false;
            try{
                const auto end=GetTickCount64()+3000;do{observed=action=="retire"?adapter->retire():adapter->poll(1000);
                    if(text(observed,"status")!="accepted_running")break;
                }while(GetTickCount64()<end);
            }catch(const std::bad_alloc&){allocation_failed=true;}
            fail_next_allocation=false;allocation_checkpoint=0;
            if(allocation_failed){
                row.put("allocation_source",source()).put("allocation_snapshot_preserved",V::boolean_value(capture.snapshot()==before))
                    .put("allocation_evidence_preserved",V::boolean_value(adapter->evidence()==old_evidence));
                observed=adapter->poll(1000);
            }
            row.put("allocation_failed",V::boolean_value(allocation_failed));workers.items.push_back(observed);
            const auto duplicate_view=capture.snapshot();const auto duplicate_evidence=adapter->evidence();workers.items.push_back(adapter->poll());
            row.put("duplicate_snapshot_preserved",V::boolean_value(capture.snapshot()==duplicate_view)).put("duplicate_evidence_preserved",V::boolean_value(adapter->evidence()==duplicate_evidence));
            if(capture.snapshot()->sources[0].outstanding){
                bool refused=false;try{adapter->start(n::StorageQueryPolicy{},fixture);}catch(const std::invalid_argument&){refused=true;}
                row.put("replacement_refused",V::boolean_value(refused)).put("live_source",source());workers.items.push_back(adapter->retire());
            }
            require(!capture.snapshot()->sources[0].outstanding,"fixture_reader_outstanding");
        }
        auto evidence=adapter->evidence();const auto graph=capture.snapshot()->graph;const auto before_resolve=capture.snapshot();bool domains=true;
        for(const auto& node:graph.nodes)if(node.scope==disked::GraphNodeScope::Observation)domains=domains && node.observation.domain==capture.epoch_domain();
        auto resolved=V::array(),artifacts=V::object();for(const auto& node:graph.nodes)if(node.kind=="storage-identity-observation"){
            require(bool(evidence),"fixture_missing_evidence");for(const auto& entry:get(node.observation.payload,"references").fields){
                const auto kind=text(entry.second,"kind"),digest=text(entry.second,"digest"),artifact=kind+":"+digest;
                const auto& value=evidence->resolve(kind,digest);if(!artifacts.find(artifact))artifacts.put(artifact,value);
                resolved.items.push_back(V::object().put("node",V::string(node.id)).put("name",V::string(entry.first)).put("reference",entry.second).put("artifact",V::string(artifact)));}
        }
        if(evidence){
            const auto& projection=*evidence->current();row.put("frame",projection.frame().frame().value()).put("identity",projection.identity().value()).put("context",projection.frame().context())
                .put("comparisons",projection.comparisons()).put("evidence_capture",V::string(std::to_string(projection.frame().key().capture)))
                .put("complete_digest",evidence->last_complete()?V::string(n::storage_identity_digest(evidence->last_complete()->identity())):V{});
            bool unknown=false;try{evidence->resolve("file","sha256:"+std::string(64,'0'));}catch(const std::invalid_argument&){unknown=true;}
            row.put("unknown_reference_refused",V::boolean_value(unknown));
        }
        row.put("workers",workers).put("source",source()).put("owner_changed",V::boolean_value(evidence!=old_evidence))
            .put("domains_retained",V::boolean_value(domains))
            .put("graph",disked::GraphSnapshot::create(graph,capture.snapshot()->capture)->value()).put("resolved",resolved).put("artifacts",artifacts)
            .put("inspections",inspect_storage(graph,registry,discovery)).put("pure_retrieval_and_presentation",V::boolean_value(capture.snapshot()==before_resolve && adapter->evidence()==evidence));
        if(index && !previous_graph.nodes.empty())row.put("focus",storage_focus(previous_graph,graph,registry,"storage-identity-observation"));
        std::weak_ptr<const n::StorageGraphEvidence> old=old_evidence;old_evidence.reset();row.put("old_evidence_expired",V::boolean_value(old.expired() || old.lock()==evidence));
        if(stage.find("retain") && get(stage,"retain").boolean)retained=evidence;
        previous_graph=graph;rows.items.push_back(std::move(row));
    }
    adapter.reset();bool retained_resolves=false;if(retained){const auto digest=n::storage_identity_digest(retained->current()->identity());retained_resolves=retained->resolve("identity",digest).kind==V::Kind::object;}
    return V::object().put("status",V::string("observed")).put("stages",rows).put("retained_after_adapter_destruction",V::boolean_value(retained_resolves))
        .put("allocation_checkpoint_hits",V::string(std::to_string(allocation_checkpoint_hits))).put("pointer_bytes",V::string(std::to_string(sizeof(void*))))
        .put("frontend_budget_ready",V::boolean_value(budget.ready())).put("api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
}
#endif

#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
V inventory_port(const V& input,const disked::WindowsMemoryBudget& budget){
    const auto& reg=get(input,"registry");disked::Registry registry{get(reg,"commands"),get(reg,"syntax"),get(reg,"schemas")};
    auto commands=registry.commands;for(auto& c:commands.items)c.put("availability",V::string(disked::FrontendSession::handles(text(c,"id"))?"available":"unavailable"));
    const auto discovery=V::object().put("commands",commands);const auto composition=text(input,"composition");
    require(composition=="metadata" || composition=="identity-frame" || composition=="identity","fixture_composition");
    auto service=composition=="metadata"?std::unique_ptr<n::InventorySession>(new n::InventorySession()):
        std::unique_ptr<n::InventorySession>(new n::InventorySession(n::StorageFrameProfile::IdentityLayout,
            composition=="identity"?n::StorageGraphProjection::Identity:n::StorageGraphProjection::Frame));
    const auto port=service->port();bool defer=false;unsigned callbacks=0,health_calls=0;
    disked::FrontendSession frontend(registry,*port.graph(),[port,&defer,&callbacks](){++callbacks;return defer?std::shared_ptr<const disked::GraphInput>{}:port.graph();},
        [&](const std::string& id,const V&,const std::string&,const V&){++health_calls;return disked::completed(id,V::object());},disked::FrontendProfile::CachedObservations);
    auto by_value=frontend.snapshot();require(bool(by_value->observation_owner()),"fixture_initial_owner");by_value.reset();
    auto initial=disked::GraphSnapshot::create(*port.graph(),1);require(!initial->observation_owner(),"fixture_value_owner");initial.reset();
    bool null_refused=false;try{disked::GraphSnapshot::create_owned({},1);}catch(const std::invalid_argument& e){null_refused=std::string(e.what())=="graph_owner_missing";}
    const auto& stages=get(input,"stages");require(stages.kind==V::Kind::array && !stages.items.empty() && stages.items.size()<=4,"fixture_stages");
    auto state=[&](){const auto view=service->capture();auto rows=V::array();for(const auto& source:view->sources)rows.items.push_back(V::object()
        .put("id",V::string(source.id)).put("state",V::string(disked::source_state_name(source.state))).put("outstanding",V::boolean_value(source.outstanding))
        .put("worker",V::string(std::to_string(source.attempt.worker))).put("attempt_capture",V::string(std::to_string(source.attempt.capture))));
        return V::object().put("capture",V::string(std::to_string(view->capture))).put("sequence",V::string(std::to_string(view->sequence))).put("sources",rows);};
    auto rows=V::array();disked::GraphInput previous_graph;std::weak_ptr<const n::InventoryPublication> previous;
    for(std::size_t index=0;index<stages.items.size();++index){
        const auto& stage=stages.items[index];const auto& ns=get(stage,"namespace");const auto& storage=get(stage,"storage");
        auto held=frontend.snapshot();previous=port.publication();bool held_bindings=true;
        if(index)service->next_capture();
        std::vector<n::StorageComparisonSelection> selections;
        if(const auto* declarations=stage.find("comparisons"))for(const auto& d:declarations->items){
            std::string prior;for(const auto& node:port.graph()->nodes)if(node.kind=="storage-identity-observation" && node.observation.payload.find("subject_key") && text(node.observation.payload,"subject_key")==text(d,"previous_subject")){
                prior=text(get(get(node.observation.payload,"references"),"identity"),"digest");break;}
            selections.push_back({d.find("previous_digest")?text(d,"previous_digest"):prior,text(d,"previous_subject"),text(d,"current_subject")});
        }
        service->start_namespace(n::InventoryPolicy{},ns);service->start_storage(n::StorageQueryPolicy{},storage,selections);
        auto row=V::object(),workers=V::array();workers.items.push_back(service->poll(n::InventorySource::Namespace));workers.items.push_back(service->poll(n::InventorySource::Storage));
        require(service->publish(),"fixture_pending_publication");frontend.refresh_observations();
        row.put("pending",state()).put("pending_graph",frontend.snapshot()->value());
        auto pending_pub=port.publication();auto pending_capture=service->capture();const auto pending_graph=port.graph();
        inspect_session(frontend,registry,discovery,"namespace");inspect_session(frontend,registry,discovery,"storage");
        row.put("pending_cached_pure",V::boolean_value(service->capture()==pending_capture && port.publication()==pending_pub && port.graph()==pending_graph));
        const auto na=stage.find("namespace_action")?text(stage,"namespace_action"):"complete",sa=stage.find("storage_action")?text(stage,"storage_action"):"complete";
        if(na=="cancel-before")service->cancel(n::InventorySource::Namespace);if(sa=="cancel-before")service->cancel(n::InventorySource::Storage);
        service->release(n::InventorySource::Namespace);service->release(n::InventorySource::Storage);
        if(na=="superseded" || sa=="superseded"){require(service->wait_entered(n::InventorySource::Namespace,1000) && service->wait_entered(n::InventorySource::Storage,1000),"fixture_wait_entered");service->next_capture();}
        for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            const auto action=source==n::InventorySource::Namespace?na:sa;
            if(action=="timeout" || action=="cancel-during" || action=="retire"){
                require(service->wait_entered(source,1000),"fixture_wait_entered");service->timeout(source);if(action=="cancel-during")service->cancel(source);
                row.put(source==n::InventorySource::Namespace?"namespace_waiting":"storage_waiting",state());
            }
        }
        for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            const auto action=source==n::InventorySource::Namespace?na:sa;
            V observed;const auto until=GetTickCount64()+5000;
            do{observed=action=="retire"?service->retire(source):service->poll(source,1000);if(text(observed,"status")!="accepted_running")break;}while(GetTickCount64()<until);
            require(text(observed,"status")!="accepted_running","fixture_reader_result");workers.items.push_back(observed);
        }
        const auto prepared_capture=service->capture();const auto before_pub=port.publication();bool provider_failed=false;
        if(stage.find("provider_allocation"))fail_inventory_publication=true;
        try{service->publish();}catch(const std::bad_alloc&){provider_failed=true;}
        fail_next_allocation=false;fail_inventory_publication=false;
        row.put("provider_allocation_failed",V::boolean_value(provider_failed));
        if(provider_failed){row.put("provider_failure_preserved",V::boolean_value(port.publication()==before_pub && service->capture()==prepared_capture && service->needs_publication()));require(service->publish(),"fixture_provider_retry");}
        auto accepted=port.graph();auto accepted_publication=port.publication();
        fail_next_allocation=true;const auto cached=port.graph();const bool getter_no_allocation=fail_next_allocation && cached==accepted;fail_next_allocation=false;
        row.put("getter_no_allocation",V::boolean_value(getter_no_allocation));
        defer=true;const auto before_front=frontend.snapshot();
        if(!before_front->value().find("nodes")->items.empty())frontend.act({disked::ActionKind::Select,text(before_front->value().find("nodes")->items.front(),"id"),before_front->revision(),"allocation:select"});
        const auto selection=frontend.selection();defer=false;bool frontend_failed=false;
        if(stage.find("frontend_allocation"))fail_next_allocation=true;
        try{frontend.refresh_observations();}catch(const std::bad_alloc&){frontend_failed=true;}
        fail_next_allocation=false;row.put("frontend_allocation_failed",V::boolean_value(frontend_failed));
        if(frontend_failed){defer=true;row.put("frontend_failure_preserved",V::boolean_value(frontend.snapshot()==before_front && disked::json::dump(frontend.selection())==disked::json::dump(selection) && port.graph()==accepted));defer=false;require(frontend.refresh_observations(),"fixture_frontend_retry");}
        auto snap=frontend.snapshot();row.put("delivered_owner",V::boolean_value(snap->observation_owner()==accepted));
        const auto current_view=service->capture();auto bindings=V::array(),artifacts=V::object(),resolved=V::array();bool domain=true;
        for(const auto& node:accepted->nodes){const auto& frame=accepted_publication->frame(node.id);const auto fd=disked::digest_sha256(disked::json::dump(frame,node.observation.source=="storage"?n::storage_observation_limits():n::volume_inventory_limits()));
            const auto artifact="frame:"+fd;if(!artifacts.find(artifact))artifacts.put(artifact,frame);
            bindings.items.push_back(V::object().put("node",V::string(node.id)).put("artifact",V::string(artifact)).put("context",get(node.observation.payload,"worker_context")));
            domain=domain && node.observation.domain==current_view->sources[0].attempt.domain;
            if(node.kind=="storage-identity-observation")for(const auto& ref:get(node.observation.payload,"references").fields){const auto name=text(ref.second,"kind")+":"+text(ref.second,"digest");
                if(!artifacts.find(name))artifacts.put(name,accepted_publication->resolve(node.id,ref.first));resolved.items.push_back(V::object().put("node",V::string(node.id)).put("name",V::string(ref.first)).put("reference",ref.second).put("artifact",V::string(name)));}
        }
        bool missing=false,reference=false;try{accepted_publication->frame("missing:node");}catch(const std::invalid_argument& e){missing=std::string(e.what())=="inventory_node";}
        if(!accepted->nodes.empty())try{accepted_publication->resolve(accepted->nodes.front().id,"missing-reference");}catch(const std::invalid_argument& e){reference=std::string(e.what())=="inventory_reference";}
        row.put("state",state()).put("graph",snap->value()).put("bindings",bindings).put("artifacts",artifacts).put("resolved",resolved)
            .put("namespace_inspections",inspect_session(frontend,registry,discovery,"namespace")).put("storage_inspections",inspect_session(frontend,registry,discovery,"storage"))
            .put("domains_retained",V::boolean_value(domain)).put("missing_node_refused",V::boolean_value(missing)).put("missing_reference_refused",V::boolean_value(accepted->nodes.empty() || reference))
            .put("retrieval_and_presentation_pure",V::boolean_value(service->capture()==current_view && port.publication()==accepted_publication));
        if(index){row.put("namespace_focus",storage_focus(previous_graph,*accepted,registry,"nt-volume-observation","namespace"));row.put("storage_focus",storage_focus(previous_graph,*accepted,registry,composition=="identity"?"storage-identity-observation":"storage-partition-observation"));}
        auto old=previous.lock();require(bool(old),"fixture_old_publication_lifetime");
        for(const auto& node:held->value().find("nodes")->items){const auto id=text(node,"id");const auto& properties=get(node,"properties");const auto& binding=get(properties,"observation_binding");const auto& frame=old->frame(id);
            held_bindings=held_bindings && disked::digest_sha256(disked::json::dump(frame,text(binding,"source")=="storage"?n::storage_observation_limits():n::volume_inventory_limits()))==text(binding,"frame_digest");
            if(text(node,"kind")=="storage-identity-observation")for(const auto& ref:get(get(properties,"observation"),"references").fields){
                auto limits=disked::json::Limits{};limits.bytes=8388608;limits.values=262144;limits.depth=35;limits.string_bytes=1048576;
                held_bindings=held_bindings && disked::digest_sha256(disked::json::dump(old->resolve(id,ref.first),limits))==text(ref.second,"digest");}
        }
        row.put("held_snapshot_retains_publication",V::boolean_value(held_bindings && bool(held->observation_owner())));old.reset();held.reset();
        row.put("old_publication_released",V::boolean_value(previous.expired()));previous_graph=*accepted;
        bool replacement_refused=true;for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            const auto slot=source==n::InventorySource::Namespace?0u:1u;if(!service->capture()->sources[slot].outstanding)continue;
            bool refused=false;try{if(source==n::InventorySource::Namespace)service->start_namespace(n::InventoryPolicy{},ns);else service->start_storage(n::StorageQueryPolicy{},storage);}catch(const std::invalid_argument&){refused=true;}
            replacement_refused=replacement_refused && refused;workers.items.push_back(service->retire(source));
        }
        row.put("replacement_refused",V::boolean_value(replacement_refused)).put("retired",state()).put("workers",workers);
        require(!service->capture()->sources[0].outstanding && !service->capture()->sources[1].outstanding,"fixture_outstanding");
        service->publish();frontend.refresh_observations();rows.items.push_back(std::move(row));
    }
    const auto final_view=service->capture();auto final_pub=port.publication();auto final_graph=port.graph();auto final_snapshot=frontend.snapshot();service.reset();
    bool retained=port.graph()==final_graph && port.publication()==final_pub && final_pub->view()==final_view && final_snapshot->observation_owner()==final_graph;
    for(const auto& node:final_graph->nodes){final_pub->frame(node.id);if(node.kind=="storage-identity-observation")for(const auto& ref:get(node.observation.payload,"references").fields)final_pub->resolve(node.id,ref.first);}inspect_session(frontend,registry,discovery,"namespace");inspect_session(frontend,registry,discovery,"storage");
    return V::object().put("stages",rows).put("composition",V::string(composition)).put("retained_after_session_destruction",V::boolean_value(retained))
        .put("null_owner_refused",V::boolean_value(null_refused)).put("value_construction_unowned",V::boolean_value(true)).put("callbacks",V::string(std::to_string(callbacks)))
        .put("health_calls",V::string(std::to_string(health_calls))).put("allocation_checkpoint_hits",V::string(std::to_string(inventory_allocation_hits)))
        .put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("frontend_budget_ready",V::boolean_value(budget.ready()))
        .put("namespace_api_calls",V::string(std::to_string(disked::nt_fixture::call_count()))).put("storage_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())));
}
#endif

V exercise(const V& input,const disked::WindowsMemoryBudget& budget) {
    const auto mode=text(input,"mode");const auto& reg=get(input,"registry");
#if defined(DISKED_NT_IDENTITY_PROJECTION_TESTING)
    if(mode=="identity-projection")return identity_projection(input,budget);
#endif
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
    if(mode=="identity-adapter")return identity_adapter(input,budget);
#endif
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
    if(mode=="inventory-port")return inventory_port(input,budget);
#endif
    disked::Registry registry{get(reg,"commands"),get(reg,"syntax"),get(reg,"schemas")};
    auto commands=registry.commands;for(auto& c:commands.items)c.put("availability",V::string(disked::FrontendSession::handles(text(c,"id"))?"available":"unavailable"));
    auto discovery=V::object().put("commands",commands);
    if(mode=="cli-limit") {
        auto graph=synthetic(input);require(graph.nodes.size()==80,"fixture_cli_shape");
        for(auto& node:graph.nodes) {node.label="D";node.observation.payload.put("text",V::string(std::string(8800,127)));node.id=disked::observation_node_id(node);}
        disked::FrontendSession session(registry,graph,{},{},disked::FrontendProfile::CachedObservations);const auto before=session.snapshot();
        const auto outcome=session.dispatch("cli:limit","topology.show",V::object());disked::ParseResult parsed;parsed.command_id="topology.show";
        disked::InvocationHost host;const auto unavailable=disked::cli_text(outcome,parsed,host,registry,false,false);require(!unavailable.available,"fixture_cli_unusable_channel");
        host.output_usable=true;auto errors=V::array();
        for(bool background:{false,true}) {std::string reason;try{disked::cli_text(outcome,parsed,host,registry,background,false);}catch(const std::length_error& e){reason=e.what();}
            require(reason=="presentation_limit","fixture_cli_display_limit");errors.items.push_back(V::string(reason));}
        require(session.snapshot()==before,"fixture_cli_changed_graph");
        return V::object().put("limits",errors).put("raw_view_bytes",V::string(std::to_string(disked::json::dump(outcome.response,disked::cached_observation_view_limits()).size())))
            .put("chunks",V::string("80")).put("chunk_bytes",V::string("8800")).put("glyph",V::string("127")).put("unavailable",V::boolean_value(unavailable.available))
            .put("unchanged",V::boolean_value(true)).put("frontend_budget_ready",V::boolean_value(budget.ready())).put("child_launches",V::string("0"));
    }
    disked::ObservationCapture capture({"namespace","storage","peer"},disked::GraphProfile::Observations);
    const auto pk=capture.start("peer");disked::GraphInput pg;pg.nodes.push_back({"fake:peer","block-device","fixture:peer","1","peer","current","4096",{}});capture.finish(pk,pg);
    auto initial=mode=="synthetic"?synthetic(input):capture.snapshot()->graph;
    if(mode=="history") {
        auto graph=synthetic(input);disked::FrontendSession session(registry,graph,{},{},disked::FrontendProfile::CachedObservations);
        const auto first=session.snapshot();const auto old=graph.nodes.front().id;session.act({disked::ActionKind::Select,old,first->revision(),"history:select"});
        for(unsigned i=2;i<=1027;++i) {
            graph.nodes.front().observation.capture=i;graph.nodes.front().id=disked::observation_node_id(graph.nodes.front());session.publish(graph);
        }
        const auto after_observations=session.snapshot();
        for(unsigned i=1;i<=1024;++i) {
            auto next=graph;next.nodes.push_back({"fake:history:"+std::to_string(i),"block-device","fixture:history:"+std::to_string(i),"1","peer","current","4096",{}});session.publish(next);
        }
        const auto before_limit=session.snapshot();auto next=graph;next.nodes.push_back({"fake:history:1025","block-device","fixture:history:1025","1","peer","current","4096",{}});
        std::string limit;try{session.publish(next);}catch(const std::invalid_argument& e){limit=e.what();}require(session.snapshot()==before_limit,"fixture_history_not_atomic");
        next.nodes.back().id="fake:history:1";next.nodes.back().identity="fixture:replacement";std::string reuse;
        try{session.publish(next);}catch(const std::invalid_argument& e){reuse=e.what();}require(session.snapshot()==before_limit,"fixture_reuse_not_atomic");
        next=graph;next.nodes.front().identity="physical-claim";std::string media;
        try{session.publish(next);}catch(const std::invalid_argument& e){media=e.what();}require(session.snapshot()==before_limit,"fixture_media_not_atomic");
        return V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("selection",session.selection()).put("first",first->value()).put("after_observations",after_observations->value())
            .put("limit",V::string(limit)).put("reuse",V::string(reuse)).put("media",V::string(media)).put("frontend_budget_ready",V::boolean_value(budget.ready()));
    }
    if(mode=="default") {
        try {disked::FrontendSession denied(registry,initial);throw std::runtime_error("fixture_profile_admitted");}
        catch(const std::invalid_argument& e){return V::object().put("reason",V::string(e.what())).put("child_launches",V::string("0"));}
    }
    std::shared_ptr<const disked::GraphInput> pending;bool offer=true;unsigned polls=0,health_calls=0;
    disked::FrontendSession session(registry,initial,[&]{++polls;return offer?pending:nullptr;},
        [&](const std::string& id,const V&,const std::string&,const V&){++health_calls;return disked::completed(id,V::object().put("fake_health",V::boolean_value(true)));},disked::FrontendProfile::CachedObservations);
    auto workers=V::array();n::NamespaceGraphAdapter ns(capture,"namespace");n::StorageGraphAdapter storage(capture,"storage",storage_profile);
    auto pending_lifecycle=V::object();
    if(mode=="owned" || mode=="pending") {
        workers.items.push_back(owned(ns,n::InventoryPolicy{},get(input,"namespace")));
        if(mode=="owned")workers.items.push_back(owned(storage,n::StorageQueryPolicy{},get(input,"storage")));
        else {
            storage.start(n::StorageQueryPolicy{},get(input,"storage"));storage.release();require(storage.wait_entered(1000),"fixture_reader_not_entered");storage.timeout();
            pending_lifecycle.put("before",storage.poll());
        }
        pending=std::make_shared<const disked::GraphInput>(capture.snapshot()->graph);
    }
    const auto views_started=GetTickCount64();
    auto snapshot=session.snapshot();std::string id;std::size_t ordinal=0;
#if defined(DISKED_NT_IDENTITY_FRONTEND_TESTING)
    const auto retained_graph=mode=="synthetic"?initial:capture.snapshot()->graph;
#endif
    const auto& nodes=get(snapshot->value(),"nodes").items;
    for(;ordinal<nodes.size();++ordinal)if(text(get(nodes[ordinal],"properties"),"scope")=="observation-only"){id=text(nodes[ordinal],"id");break;}
    require(!id.empty(),"fixture_no_observations");
    auto dispatch=[&](const std::string& request,const std::string& command,const V& parameters,const std::string& revision)->disked::Submission {return session.dispatch(request,command,parameters,revision);};
    const auto selected=session.act({disked::ActionKind::Select,id,snapshot->revision(),"direct:select"});
    auto direct=session.act({disked::ActionKind::Inspect,id,snapshot->revision(),"direct:inspect"});
    disked::GuiModel gui(session,registry,discovery,dispatch);gui.focus(id);gui.open();const auto gui_inspect=get(gui.state(),"last_outcome");
    disked::TuiModel tui(session,registry,discovery,dispatch);for(std::size_t i=0;i<ordinal;++i)key(tui,disked::TextKey::Down);key(tui,disked::TextKey::Enter);const auto tui_inspect=get(tui.state(),"last_outcome");
    disked::ShellModel shell(session,registry,discovery,dispatch,false);submit(shell,"target inspect "+id);const auto shell_inspect=get(shell.state(),"last_outcome");
    auto observations=V::object().put("selected",selected.response).put("direct",direct.response).put("gui",gui_inspect).put("tui",tui_inspect).put("shell",shell_inspect);
    auto health=session.dispatch("health","health.assess",V::object().put("target_id",V::string(id)));
    auto capability=session.dispatch("capability","capability.explain",V::object().put("target_id",V::string(id)).put("operation",V::string("health.assess")));
    gui.stage("health.assess",V::object());tui.stage("health.assess",V::object());
    auto forms=V::object().put("gui",compact_state(gui.state())).put("tui",compact_state(tui.state()));
    auto completion=[&](const char* command) {disked::ShellModel s(session,registry,discovery,dispatch,false);s.input({disked::TextKey::Text,command,false});key(s,disked::TextKey::Tab);return compact_state(s.state());};
    auto completions=V::object().put("inspect",completion("target inspect ")).put("health",completion("health assess "));
    const auto list=session.dispatch("list","target.list",V::object());const auto topology=session.dispatch("topology","topology.show",V::object());
    gui.stage("topology.show",V::object());gui.review();gui.submit();tui.stage("topology.show",V::object());key(tui,disked::TextKey::F9);key(tui,disked::TextKey::F9);
    disked::ShellModel large_shell(session,registry,discovery,dispatch,false);submit(large_shell,"topology show");std::uint64_t after=0;
    auto rendered=V::object().put("gui",V::string(gui.detail_text())).put("tui",lines(tui.render(80,25,true))).put("shell",lines(large_shell.linear_records(after)))
        .put("shell_state",compact_state(large_shell.state()));
    auto screen=V::object().put("tui",lines(tui.render(80,25,false))).put("shell",lines(large_shell.render(80,25,false)));
    auto rows=gui.rows();
    auto retry=V::object();
    if(mode=="owned") {
        // Stage all three frontends against the old snapshot before explicit
        // capture. They do not poll workers, launch replacements or rebase.
        gui.focus(id);gui.navigate(false);tui.input({disked::TextKey::F3,"",false});
        disked::ShellModel staged(session,registry,discovery,dispatch,false);staged.input({disked::TextKey::Text,"target inspect "+id,false});key(staged,disked::TextKey::F9);
        capture.next_capture();workers.items.push_back(owned(ns,n::InventoryPolicy{},get(input,"namespace")));
        const auto* next=input.find("storage_next");workers.items.push_back(owned(storage,n::StorageQueryPolicy{},next?*next:get(input,"storage")));
        pending=std::make_shared<const disked::GraphInput>(capture.snapshot()->graph);
        gui.open();key(tui,disked::TextKey::Enter);key(staged,disked::TextKey::F9);
        retry.put("stale",V::object().put("gui",get(gui.state(),"last_outcome")).put("tui",get(tui.state(),"last_outcome")).put("shell",get(staged.state(),"last_outcome")));
        gui.refresh();key(tui,disked::TextKey::F5);key(staged,disked::TextKey::F5);
        retry.put("refreshed",V::object().put("gui",compact_state(gui.state())).put("tui",compact_state(tui.state())).put("shell",compact_state(staged.state())));
        retry.put("current_graph",session.snapshot()->value()).put("selection",session.selection()).put("old_graph",snapshot->value());
        require(!capture.snapshot()->sources[0].outstanding && !capture.snapshot()->sources[1].outstanding,"fixture_capture_outstanding");
    }
    auto prior=session.snapshot();const auto prior_selection=disked::json::dump(session.selection());
    pending=std::make_shared<const disked::GraphInput>(pending?*pending:initial);
    fail_next_allocation=true;bool allocation_failed=false;try{session.refresh_observations();}catch(const std::bad_alloc&){allocation_failed=true;}fail_next_allocation=false;
    offer=false;require(allocation_failed && session.snapshot()==prior && disked::json::dump(session.selection())==prior_selection,"fixture_allocation_not_atomic");
    offer=true;require(session.refresh_observations(),"fixture_pointer_consumed");auto retried=session.snapshot();
    retry.put("allocation_failed",V::boolean_value(allocation_failed)).put("before_capture",get(prior->value(),"capture_id")).put("retry_capture",get(retried->value(),"capture_id"));
    auto invalid=*pending;invalid.nodes.push_back(invalid.nodes.front());pending=std::make_shared<const disked::GraphInput>(invalid);
    std::string reason;try{session.refresh_observations();}catch(const std::invalid_argument& e){reason=e.what();}
    offer=false;require(!reason.empty() && session.snapshot()==retried && disked::json::dump(session.selection())==prior_selection,"fixture_validation_not_atomic");
    retry.put("rejected_publication",V::string(reason)).put("failure_capture",get(session.snapshot()->value(),"capture_id"));
    // Actual current/earlier model retention with distinct request IDs. The
    // completion port is an in-memory fixture, not an operation or transport.
    const auto pair_result=get(session.dispatch("pair","topology.show",V::object()).response,"result");
    bool defer=true,ready=false;disked::Outcome queued;
    auto handler=[&](const std::string& request,const std::string&,const V&,const std::string&)->disked::Submission {
        if(defer){queued=disked::completed(request,pair_result);return disked::Submission::deferred();}return disked::completed(request,pair_result);
    };
    auto poll=[&](disked::Outcome& value){if(!ready)return false;ready=false;value=std::move(queued);return true;};
    disked::GuiModel paired_gui(session,registry,discovery,handler,poll);paired_gui.stage("topology.show",V::object());paired_gui.review();paired_gui.submit();paired_gui.navigate(false);ready=true;require(paired_gui.tick(),"fixture_gui_completion_missing");
    defer=false;paired_gui.stage("topology.show",V::object());paired_gui.review();paired_gui.submit();
    defer=true;disked::TuiModel paired_tui(session,registry,discovery,handler,poll);paired_tui.stage("topology.show",V::object());key(paired_tui,disked::TextKey::F9);key(paired_tui,disked::TextKey::F9);key(paired_tui,disked::TextKey::F3);ready=true;require(paired_tui.tick(),"fixture_tui_completion_missing");
    defer=false;paired_tui.stage("topology.show",V::object());key(paired_tui,disked::TextKey::F9);key(paired_tui,disked::TextKey::F9);
    auto paired=V::object().put("basis",pair_result).put("gui",V::string(paired_gui.detail_text())).put("tui",lines(paired_tui.render(80,25,true)));
    std::string wire;try{disked::response_frame(topology.response);wire="within_existing_limit";}catch(const disked::json::Error& e){wire=e.code;}
    if(mode=="pending") {
        pending_lifecycle.put("views_elapsed_ms",V::string(std::to_string(GetTickCount64()-views_started))).put("during",storage.poll());
        bool replacement=false;try{storage.start(n::StorageQueryPolicy{},get(input,"storage"));}catch(const std::invalid_argument&){replacement=true;}
        require(replacement && capture.snapshot()->sources[1].outstanding,"fixture_reader_replaced_by_ui");
        pending_lifecycle.put("replacement_refused",V::boolean_value(replacement)).put("after",storage.retire());
        require(!capture.snapshot()->sources[1].outstanding,"fixture_reader_retirement_unobserved");
    }
    auto output=V::object().put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("mode",V::string(mode)).put("graph",snapshot->value()).put("workers",workers)
        .put("inspections",observations).put("list",list.response).put("topology",topology.response).put("rows",rows).put("health",health.response).put("health_calls",V::string(std::to_string(health_calls)))
        .put("capability",capability.response).put("forms",forms).put("completions",completions).put("rendered",rendered).put("screen",screen).put("retry",retry).put("paired",paired)
        .put("wire_result",V::string(wire)).put("polls",V::string(std::to_string(polls))).put("pending_lifecycle",pending_lifecycle).put("frontend_budget_ready",V::boolean_value(budget.ready())).put("frontend_memory_bytes",V::string(std::to_string(disked::WindowsMemoryBudget::limit_bytes())));
    output.put("cli_topology",cli_view(topology,"topology.show",registry));
#if defined(DISKED_NT_IDENTITY_FRONTEND_TESTING)
    output.put("storage_profile",V::string("identity-layout")).put("storage_inspections",inspect_storage(retained_graph,registry,discovery))
        .put("storage_current_inspections",inspect_storage(capture.snapshot()->graph,registry,discovery));
    if(mode=="owned")output.put("storage_focus",storage_focus(retained_graph,capture.snapshot()->graph,registry));
#endif
    return output;
}
}
int wmain(int argc,wchar_t** argv) {
#if defined(DISKED_NT_IDENTITY_FRONTEND_TESTING)
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
#endif
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_storage_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);});
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_fixture::api(v,notify);});
    if(argc!=1)return 2;disked::WindowsMemoryBudget budget;if(!budget.ready())return 7;
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    try {
        std::string data;char block[8192];for(;;){const auto bytes=std::fread(block,1,sizeof(block),stdin);if(data.size()+bytes>1048576)return 2;data.append(block,bytes);if(bytes<sizeof(block)){if(std::ferror(stdin))return 2;break;}}
        disked::json::Limits l;l.bytes=1048576;l.values=131072;l.depth=35;const auto input=disked::json::parse(data,l);const auto mode=text(input,"mode");
        bool allowed=mode=="owned" || mode=="pending" || mode=="synthetic" || mode=="default" || mode=="history" || mode=="cli-limit";
#if defined(DISKED_NT_IDENTITY_PROJECTION_TESTING)
        allowed=allowed || mode=="identity-projection";
#endif
#if defined(DISKED_NT_IDENTITY_ADAPTER_TESTING)
        allowed=allowed || mode=="identity-adapter";
#endif
#if defined(DISKED_NT_INVENTORY_PORT_TESTING)
        allowed=allowed || mode=="inventory-port";
#endif
        if(!allowed)throw std::invalid_argument("fixture_mode");const auto result=exercise(input,budget);print(result);
        return result.find("status") && text(result,"status")=="refused"?3:0;
    }catch(const std::exception& e){fail_next_allocation=false;print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
