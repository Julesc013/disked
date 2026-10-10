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
#include <cstdio>
#include <cstdlib>
#include <new>
#include <io.h>
#include <fcntl.h>

// Selected controller-only publication allocation failure, not an allocator
// replacement, exhaustiveness claim or a worker/storage failure.
namespace {bool fail_next_allocation=false;}
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
V inspect_storage(const disked::GraphInput& graph,const disked::Registry& registry,const V& discovery) {
    unsigned calls=0;disked::FrontendSession session(registry,graph,{},[&](const std::string& id,const V&,const std::string&,const V&){++calls;return disked::completed(id,V::object());},disked::FrontendProfile::CachedObservations);
    const auto snapshot=session.snapshot();auto out=V::array();const auto& nodes=get(snapshot->value(),"nodes").items;
    for(std::size_t i=0;i<nodes.size();++i) {
        const auto& properties=get(nodes[i],"properties");if(text(properties,"scope")!="observation-only" || text(get(properties,"observation_binding"),"source")!="storage")continue;
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
    require(!calls,"fixture_storage_health_called");return out;
}
V storage_focus(const disked::GraphInput& original,const disked::GraphInput& current,const disked::Registry& registry) {
    std::string id;for(const auto& node:original.nodes)if(node.scope==disked::GraphNodeScope::Observation && node.observation.source=="storage") {
        if(id.empty() || node.kind=="storage-partition-observation")id=node.id;if(node.kind=="storage-partition-observation")break;
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
V exercise(const V& input,const disked::WindowsMemoryBudget& budget) {
    const auto mode=text(input,"mode");const auto& reg=get(input,"registry");
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
        if(mode!="owned" && mode!="pending" && mode!="synthetic" && mode!="default" && mode!="history" && mode!="cli-limit")throw std::invalid_argument("fixture_mode");print(exercise(input,budget));return 0;
    }catch(const std::exception& e){fail_next_allocation=false;print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what())));return 3;}
}
