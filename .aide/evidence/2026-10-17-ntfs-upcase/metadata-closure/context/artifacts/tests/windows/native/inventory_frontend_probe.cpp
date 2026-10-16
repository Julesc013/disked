#include "inventory_fixture.h"
#include "providers/windows/inventory_session.h"
#include "storage_fixture.h"
#include "volume_fixture.h"
#include "runtime/presentation/session.h"
#include "platform/windows/ui/gui.h"
#include "platform/windows/console/terminal.h"
#include "platform/windows/memory_budget.h"
#include <algorithm>
#include <cstdio>

namespace {
using namespace disked_inventory_fixture;
unsigned reader_starts=0;
int render(const V& input,const std::wstring& mode,const wchar_t* output,const disked::WindowsMemoryBudget& budget){
    const auto& reg=field(input,"registry");disked::Registry registry{field(reg,"commands"),field(reg,"syntax"),field(reg,"schemas")};
    const auto composition=text(input,"composition");if(composition!="metadata" && composition!="identity-frame" && composition!="identity")throw std::invalid_argument("fixture_composition");
    const auto& stages=field(input,"stages");if(stages.kind!=V::Kind::array || stages.items.empty() || stages.items.size()>3)throw std::invalid_argument("fixture_stages");
    // Validate launcher shapes before creating output or constructing readers.
    if(registry.commands.kind!=V::Kind::array || registry.syntax.kind!=V::Kind::object || registry.parameter_schemas.kind!=V::Kind::object)throw std::invalid_argument("fixture_registry");
    for(const auto& stage:stages.items)if(field(stage,"namespace").kind!=V::Kind::object || field(stage,"storage").kind!=V::Kind::object)throw std::invalid_argument("fixture_stages");
    ReceiptFile receipt(output);
    auto service=composition=="metadata"?std::unique_ptr<n::InventorySession>(new n::InventorySession()):
        std::unique_ptr<n::InventorySession>(new n::InventorySession(n::StorageFrameProfile::IdentityLayout,
            composition=="identity"?n::StorageGraphProjection::Identity:n::StorageGraphProjection::Frame));
    auto workers=V::array();
    for(std::size_t i=0;i<stages.items.size();++i){
        if(i)service->next_capture();const auto& stage=stages.items[i];
        ++reader_starts;service->start_namespace(n::InventoryPolicy{},field(stage,"namespace"));
        ++reader_starts;service->start_storage(n::StorageQueryPolicy{},field(stage,"storage"));
        workers.items.push_back(service->poll(n::InventorySource::Namespace));workers.items.push_back(service->poll(n::InventorySource::Storage));
        service->release(n::InventorySource::Namespace);service->release(n::InventorySource::Storage);
        for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            V observed;const auto until=GetTickCount64()+5000;do{observed=service->poll(source,1000);
                if(text(observed,"status")!="accepted_running")break;}while(GetTickCount64()<until);
            require(text(observed,"status")!="accepted_running","fixture_reader_result");workers.items.push_back(observed);
            const auto slot=source==n::InventorySource::Namespace?0u:1u;if(service->capture()->sources[slot].outstanding)workers.items.push_back(service->retire(source));
            require(!service->capture()->sources[slot].outstanding,"fixture_reader_outstanding");
        }
        service->publish();
    }
    const auto port=service->port();const auto publication=port.publication();const auto graph=port.graph();const auto capture=publication->view();
    auto sources=V::array();for(const auto& s:capture->sources)sources.items.push_back(V::object().put("id",V::string(s.id))
        .put("state",V::string(disked::source_state_name(s.state))).put("outstanding",V::boolean_value(s.outstanding)));
    unsigned callbacks=0,health_calls=0;disked::FrontendSession frontend(registry,*graph,[port,&callbacks](){++callbacks;return port.graph();},
        [&](const std::string& id,const V&,const std::string&,const V&){++health_calls;return disked::completed(id,V::object());},disked::FrontendProfile::CachedObservations);
    frontend.refresh_observations();auto held=frontend.snapshot();service.reset();
    auto commands=registry.commands;for(auto& c:commands.items)c.put("availability",V::string(disked::FrontendSession::handles(text(c,"id"))?"available":"unavailable"));
    const auto discovery=V::object().put("commands",commands);V initial;int exit=0;
    const auto dispatch=[&](const std::string& id,const std::string& command,const V& parameters,const std::string& revision){return frontend.dispatch(id,command,parameters,revision);};
    if(mode==L"gui")exit=disked::run_windows_gui([&](const V&){auto model=std::unique_ptr<disked::GuiModel>(new disked::GuiModel(frontend,registry,discovery,dispatch));initial=model->state();return model;});
    else if(mode==L"tui")exit=disked::run_windows_tui("linear",[&](){auto model=std::unique_ptr<disked::TuiModel>(new disked::TuiModel(frontend,registry,discovery,dispatch));initial=model->state();return model;});
    else exit=disked::run_windows_shell("linear",[&](){auto model=std::unique_ptr<disked::ShellModel>(new disked::ShellModel(frontend,registry,discovery,dispatch,false));initial=model->state();return model;});
    auto artifacts=V::object(),bindings=V::array(),resolved=V::array();
    for(const auto& node:graph->nodes){const auto& frame=publication->frame(node.id);const auto digest=disked::digest_sha256(disked::json::dump(frame,node.observation.source=="storage"?n::storage_observation_limits():n::volume_inventory_limits()));
        const auto name="frame:"+digest;if(!artifacts.find(name))artifacts.put(name,frame);
        bindings.items.push_back(V::object().put("node",V::string(node.id)).put("artifact",V::string(name)).put("context",field(node.observation.payload,"worker_context")));
        if(node.kind=="storage-identity-observation")for(const auto& ref:field(node.observation.payload,"references").fields){
            const auto key=text(ref.second,"kind")+":"+text(ref.second,"digest");if(!artifacts.find(key))artifacts.put(key,publication->resolve(node.id,ref.first));
            resolved.items.push_back(V::object().put("node",V::string(node.id)).put("name",V::string(ref.first)).put("reference",ref.second).put("artifact",V::string(key)));}
    }
    const auto final=frontend.snapshot();const bool retained=final==held && final->observation_owner()==graph && port.publication()==publication && port.graph()==graph;
    receipt.write(V::object().put("renderer_exit",V::string(std::to_string(exit))).put("composition",V::string(composition)).put("graph",final->value())
        .put("initial_model_state",initial).put("selection",frontend.selection()).put("sources",sources).put("workers",workers).put("bindings",bindings).put("artifacts",artifacts).put("resolved",resolved)
        .put("retained_after_session_and_renderer",V::boolean_value(retained)).put("callbacks",V::string(std::to_string(callbacks))).put("health_calls",V::string(std::to_string(health_calls)))
        .put("namespace_api_calls",V::string(std::to_string(disked::nt_fixture::call_count()))).put("storage_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())))
        .put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("frontend_budget_ready",V::boolean_value(budget.ready())));
    return exit;
}
}
int wmain(int argc,wchar_t** argv){
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_storage_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);});
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_fixture::api(v,notify);});
    if(argc!=5 || std::wstring(argv[1])!=L"__disked_nt_inventory_renderer_fixture")return 2;
    const auto mode=std::wstring(argv[2]);if(mode!=L"gui" && mode!=L"tui" && mode!=L"shell")return 2;
    disked::WindowsMemoryBudget budget;if(!budget.ready())return 7;
    try{fixture_path(argv[3]);fixture_path(argv[4]);return render(read(argv[3]),mode,argv[4],budget);}catch(const std::exception& e){print(V::object().put("status",V::string("refused")).put("reason",V::string(e.what()))
        .put("reader_starts",V::string(std::to_string(reader_starts)))
        .put("namespace_api_calls",V::string(std::to_string(disked::nt_fixture::call_count())))
        .put("storage_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count()))));return 3;}
}
