#include "providers/windows/inventory_session.h"
#include "platform/windows/storage/observation_worker.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <stdexcept>

namespace {
using V=disked::json::Value;
namespace n=disked::nt_inventory;
const V& field(const V& v,const char* key){const auto p=v.find(key);if(!p)throw std::invalid_argument("probe_shape");return *p;}
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
std::string text(const V& v,const char* key){const auto& x=field(v,key);check(x.kind==V::Kind::string,"probe_text");return x.text;}
template<class F> bool refuses(F f){try{f();}catch(const std::invalid_argument&){return true;}return false;}
V graph(const disked::CaptureView& view){return disked::GraphSnapshot::create(view.graph,view.capture)->value();}
V finish(n::NamespaceWorker& worker){
    const auto end=GetTickCount64()+5000;
    for(;;){auto v=worker.observe(50);if(text(field(v,"worker"),"observation")=="exited")return v;check(GetTickCount64()<end,"probe_worker_deadline");}
}
V finish(n::NamespaceGraphAdapter& adapter){
    const auto end=GetTickCount64()+5000;
    for(;;){auto v=adapter.poll(50);if(text(field(v,"worker"),"observation")=="exited")return v;check(GetTickCount64()<end,"probe_graph_deadline");}
}
V finish(n::InventorySession& session){
    const auto end=GetTickCount64()+5000;
    for(;;){auto v=session.poll(n::InventorySource::Namespace,50);if(text(field(v,"worker"),"observation")=="exited")return v;check(GetTickCount64()<end,"probe_inventory_deadline");}
}
void completed(const V& observed){
    check(text(observed,"status")=="completed" && text(field(observed,"worker"),"observation")=="exited" && text(field(observed,"worker"),"exit_code")=="0","probe_completion");
    check(field(field(observed,"claims"),"live_namespace").boolean,"probe_native_capability");
    check(text(field(observed,"result"),"api_binding")=="native-win32-table","probe_native_binding");
}
V worker_case(const std::string& name){
    n::InventoryPolicy policy;
    if(name=="worker.limit")policy.volumes=1;
    if(name=="worker.no_mounts")policy.include_mounts=false;
    if(name=="worker.invalid"){
        const bool epoch=refuses([&]{n::NamespaceWorker::prepare_native(0,policy);});
        policy.volumes=65;const bool count=refuses([&]{n::NamespaceWorker::prepare_native(9,policy);});
        check(epoch && count,"probe_policy_refusal");
        return V::object().put("invalid_epoch_refused",V::boolean_value(epoch)).put("invalid_count_refused",V::boolean_value(count));
    }
    auto worker=n::NamespaceWorker::prepare_native(9,policy);auto out=V::object().put("prepared",worker->observe());
    check(worker->never_launched() && text(field(field(out,"prepared"),"worker"),"observation")=="not_started","probe_prepare");
    if(name=="worker.prepare_only")return out.put("retirement",worker->retire());
    worker->launch();
    if(name=="worker.gate_wait"){
        const auto end=GetTickCount64()+500;
        V gated;
        for(;;){gated=worker->observe(1);if(field(gated,"admitted").boolean)break;check(GetTickCount64()<end,"probe_admission_deadline");}
        check(text(field(gated,"worker"),"observation")=="running" && !worker->wait_entered(0),"probe_dispatch_gate");
        out.put("gated",gated).put("entered_before_release",V::boolean_value(false));
    }
    if(name=="worker.cancel_before")worker->cancel();
    worker->release();const auto end=finish(*worker);completed(end);
    out.put("final",end).put("entered_after",V::boolean_value(worker->wait_entered(0)));
    if(name=="worker.cancel_before")check(text(field(end,"result"),"status")=="cancelled" && !worker->wait_entered(0),"probe_cancel_before_dispatch");
    if(name=="worker.gate_wait")check(text(field(out,"gated"),"attempt_id")==text(end,"attempt_id"),"probe_same_attempt");
    return out;
}
V graph_case(const std::string& name){
    disked::ObservationCapture capture({"namespace"},disked::GraphProfile::Observations);
    n::NamespaceGraphAdapter adapter(capture,"namespace",n::NamespaceBackend::Native);n::InventoryPolicy policy;
    adapter.start_native(policy);adapter.release();const auto first=finish(adapter);completed(first);
    auto held=capture.snapshot();const auto original=disked::json::dump(graph(*held));
    auto out=V::object().put("first",first).put("graph",graph(*held));
    if(name=="graph.complete")return out;
    auto frame=adapter.frames()->current();capture.next_capture();
    if(name=="graph.partial")policy.volumes=1;
    adapter.start_native(policy);adapter.release();const auto second=finish(adapter);completed(second);
    check(original==disked::json::dump(graph(*held)),"probe_old_graph_mutated");
    check(adapter.frames()->last_complete()!=nullptr,"probe_complete_frame_missing");
    check(adapter.frames()->current()->key().capture!=frame->key().capture,"probe_new_capture");
    return out.put("second",second).put("new_graph",graph(*capture.snapshot()))
        .put("last_complete",adapter.frames()->last_complete()->value()).put("old_unchanged",V::boolean_value(true));
}
V inventory_case(){
    std::shared_ptr<const n::InventoryPublication> held;std::string original;V out=V::object();
    {
        n::InventorySession session(n::StorageFrameProfile::Metadata,n::StorageGraphProjection::Frame,n::NamespaceBackend::Native);
        auto port=session.port();const auto initial=port.publication();check(initial->view()->graph.nodes.empty(),"probe_startup_query");
        session.start_native_namespace(n::InventoryPolicy{});session.release(n::InventorySource::Namespace);const auto observed=finish(session);completed(observed);
        check(session.needs_publication() && initial->view()->graph.nodes.empty(),"probe_cached_publication");
        check(session.publish(),"probe_publication");held=port.publication();check(!held->view()->graph.nodes.empty(),"probe_empty_publication");
        const auto& first=held->frame(held->view()->graph.nodes.front().id);
        for(const auto& node:held->view()->graph.nodes)check(&held->frame(node.id)==&first,"probe_frame_owner");
        original=disked::json::dump(graph(*held->view()));
        out.put("observation",observed).put("graph",graph(*held->view())).put("frame",first);
        check(!session.publish(),"probe_spurious_publication");
    }
    check(original==disked::json::dump(graph(*held->view())),"probe_retained_publication");
    return out.put("owner_retained_after_session",V::boolean_value(true));
}
V cross_binding(){
    auto worker=n::NamespaceWorker::start_native(9,n::InventoryPolicy{});worker->release();auto observed=finish(*worker);completed(observed);
    const auto frame=field(observed,"result");
    const bool fixture=refuses([&]{n::validate_namespace_snapshot(frame,9,n::InventoryPolicy{});});
    auto injected=frame;injected.put("api_binding",V::string("injected-win32-table"));
    const bool native=refuses([&]{n::validate_native_namespace_snapshot(injected,9,n::InventoryPolicy{});});
    const bool context=refuses([&]{n::namespace_graph_context(observed);});
    auto foreign=observed;foreign.put("schema",V::string("org.disked.nt-namespace-worker-observation/1"));
    const bool reverse=refuses([&]{n::native_namespace_graph_context(foreign);});
    disked::ObservationCapture capture({"namespace"},disked::GraphProfile::Observations);
    n::NamespaceGraphAdapter adapter(capture,"namespace");
    const bool selection=refuses([&]{adapter.start_native(n::InventoryPolicy{});});
    n::NamespaceGraphAdapter actual(capture,"namespace",n::NamespaceBackend::Native);
    const bool other=refuses([&]{actual.start(n::InventoryPolicy{},V::object());});
    check(fixture && native && context && reverse && selection && other,"probe_cross_binding");
    return V::object().put("observation",observed).put("cross_binding_refusals",V::string("6"));
}
V malformed_child(const std::string& name){
    // This deliberately faulty compiled test producer bypasses parent validation.
    // The actual native child's own fixed profile must reject its input.
    n::ObservationWorkerProfile profile;
    profile.prefix="probe-native";profile.scope=name=="native.child_fixture_header"?"injected-volume-namespace":"native-volume-namespace";
    profile.input_schema=name=="native.child_fixture_header"?"org.disked.nt-namespace-worker-input/1":"org.disked.nt-native-namespace-worker-input/1";
    profile.reply_schema="org.disked.nt-native-namespace-worker-reply/1";profile.observation_schema="org.disked.nt-native-namespace-worker-observation/1";
    profile.role=L"__disked_nt_native_namespace_worker";profile.attempt_prefix="namespace-native-attempt:";profile.records_field="records";
    profile.input_mapping_bytes=98304;profile.input_limits=n::namespace_worker_limits();profile.input_limits.bytes=98300;
    profile.provider_limits=profile.input_limits;profile.reply_limits=n::namespace_worker_limits();
    profile.validate_request=[](const V&){};profile.validate_result=[](const V&,const V&){};
    auto policy=V::object().put("volumes",V::string("64")).put("mounts",V::string("64")).put("mount_units",V::string("8192")).put("include_mounts",V::boolean_value(true));
    auto provider=V::object();if(name=="native.child_unknown_input")provider.put("unadmitted",V::boolean_value(true));
    auto request=V::object().put("capture_epoch",V::string("9")).put("policy",policy).put("provider_input",provider);
    auto worker=n::ObservationWorker::prepare(request,profile);worker->launch();worker->release();
    const auto end=GetTickCount64()+5000;V observed;
    for(;;){observed=worker->observe(50);if(text(field(observed,"worker"),"observation")=="exited")break;check(GetTickCount64()<end,"probe_bad_child_deadline");}
    check(!field(observed,"admitted").boolean && field(observed,"result").kind==V::Kind::null && text(field(observed,"worker"),"exit_code")=="3","probe_native_input_admitted");
    return V::object().put("observation",observed).put("dispatch_entered",V::boolean_value(worker->wait_entered(0)));
}
V fixture_guard(){
    n::NamespaceInput request;request.capture_epoch=9;request.provider_input=V::object();
    auto worker=n::NamespaceWorker::start(request);worker->release();auto observed=finish(*worker);
    check(field(observed,"result").kind==V::Kind::null && !field(observed,"admitted").boolean && text(field(observed,"worker"),"exit_code")=="3","probe_fixture_native_accepted");
    return V::object().put("observation",observed);
}
}
int wmain(int argc,wchar_t** argv){
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_native_namespace_worker")return n::native_namespace_worker_role(argc,argv);
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V&,const std::function<void()>&){return n::native_volume_api();});
    if(_setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc!=2)return 2;
    try{
        const std::wstring raw=argv[1];std::string name;
        for(const auto unit:raw){if(unit<0x20 || unit>0x7e)return 2;name.push_back(static_cast<char>(unit));}
        V result;
        if(name=="worker.prepare_only" || name=="worker.normal" || name=="worker.no_mounts" || name=="worker.limit" || name=="worker.cancel_before" || name=="worker.gate_wait" || name=="worker.invalid")result=worker_case(name);
        else if(name=="graph.complete" || name=="graph.refresh" || name=="graph.partial")result=graph_case(name);
        else if(name=="inventory.publication")result=inventory_case();
        else if(name=="validation.cross_binding")result=cross_binding();
        else if(name=="native.child_unknown_input" || name=="native.child_fixture_header")result=malformed_child(name);
        else if(name=="fixture.native_table_guard")result=fixture_guard();else return 2;
        auto out=V::object().put("schema",V::string("org.disked.native-namespace-test/1")).put("case",V::string(name))
            .put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("result",result);
        auto limits=n::namespace_worker_limits();limits.bytes=524288;limits.values=40000;limits.depth=32;
        std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const std::exception& error){std::fprintf(stderr,"native_namespace_test: %s\n",error.what());return 4;}
}
