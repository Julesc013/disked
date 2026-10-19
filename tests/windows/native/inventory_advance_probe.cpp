#include "inventory_fixture.h"
#include "platform/windows/ui/gui.h"
#include "platform/windows/console/terminal.h"
#include "platform/windows/memory_budget.h"
#include <array>
#include <cstring>
#include <set>

namespace {
using namespace disked_inventory_fixture;
unsigned reader_starts=0;
struct Controls final {
    std::array<HANDLE,4> handles{{nullptr,nullptr,nullptr,nullptr}};
    HANDLE completion=nullptr;
    explicit Controls(const V& input,const V* completion_name=nullptr){
        const std::array<const char*,4> actions{{"advance","release","cancel","timeout"}};
        if(input.kind!=V::Kind::object || input.fields.size()!=4)throw std::invalid_argument("fixture_controls");
        const std::string prefix="DiskEd.Inventory.";std::string nonce;
        for(const auto action:actions){const auto name=text(input,action);
            if(name.size()!=prefix.size()+32+1+std::strlen(action) || name.compare(0,prefix.size(),prefix)!=0 ||
                name.substr(prefix.size()+32)!="."+std::string(action))throw std::invalid_argument("fixture_controls");
            const auto selected=name.substr(prefix.size(),32);
            if(std::any_of(selected.begin(),selected.end(),[](char c){return !(c>='0' && c<='9') && !(c>='a' && c<='f');}) ||
                (!nonce.empty() && selected!=nonce))throw std::invalid_argument("fixture_controls");nonce=selected;
        }
        if(completion_name && (completion_name->kind!=V::Kind::string || completion_name->text!=prefix+nonce+".complete"))throw std::invalid_argument("fixture_completion_control");
        try {for(std::size_t i=0;i<4;++i){const auto name=text(input,actions[i]);const std::wstring wide(name.begin(),name.end());
            handles[i]=OpenEventW(SYNCHRONIZE,FALSE,wide.c_str());if(!handles[i])throw std::invalid_argument("fixture_event_unavailable");}
            if(completion_name){const std::wstring wide(completion_name->text.begin(),completion_name->text.end());
                completion=OpenEventW(SYNCHRONIZE,FALSE,wide.c_str());if(!completion)throw std::invalid_argument("fixture_completion_unavailable");}}
        catch(...){close();throw;}
    }
    ~Controls(){close();}Controls(const Controls&)=delete;Controls& operator=(const Controls&)=delete;
    void close(){for(auto& handle:handles)if(handle){CloseHandle(handle);handle=nullptr;}if(completion){CloseHandle(completion);completion=nullptr;}}
    bool signalled(std::size_t at)const{const auto result=WaitForSingleObject(handles.at(at),0);
        if(result==WAIT_FAILED)throw std::runtime_error("fixture_event_wait");return result==WAIT_OBJECT_0;}
    bool completion_ready()const{if(!completion)return false;const auto result=WaitForSingleObject(completion,0);
        if(result==WAIT_FAILED)throw std::runtime_error("fixture_completion_wait");return result==WAIT_OBJECT_0;}
};
class Driver final {
    n::InventorySession& service_;const V& stages_;Controls& controls_;
    std::size_t stage_=0;bool active_=false,timed_out_=false,released_=false,failed_=false;
    ULONGLONG started_=0;std::array<std::string,2> previous_;
    std::vector<std::shared_ptr<const n::InventoryPublication>> publications_;
    std::vector<std::shared_ptr<const disked::GraphSnapshot>> snapshots_;
    void worker(n::InventorySource source,const V& value){const auto at=source==n::InventorySource::Namespace?0u:1u;
        const auto encoded=disked::json::dump(value,receipt_limits());if(encoded==previous_[at])return;
        if(workers.items.size()==64)throw std::length_error("fixture_worker_trace_limit");workers.items.push_back(value);previous_[at]=encoded;}
    void note(const std::string& kind){if(events.items.size()==64)throw std::length_error("fixture_event_trace_limit");
        events.items.push_back(V::object().put("kind",V::string(kind)).put("stage",V::string(std::to_string(stage_))));}
    bool outstanding()const{const auto view=service_.capture();return std::any_of(view->sources.begin(),view->sources.end(),[](const disked::CaptureSource& source){return source.outstanding;});}
    void start(){
        const auto& input=stages_.items.at(stage_);active_=true;failed_=false;timed_out_=false;released_=false;started_=GetTickCount64();previous_={{"",""}};
        ++reader_starts;service_.start_namespace(n::InventoryPolicy{},field(input,"namespace"));
        worker(n::InventorySource::Namespace,service_.poll(n::InventorySource::Namespace));
        ++reader_starts;service_.start_storage(n::StorageQueryPolicy{},field(input,"storage"));
        worker(n::InventorySource::Storage,service_.poll(n::InventorySource::Storage));note("started");
    }
    void release(){for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage})service_.release(source);released_=true;note("released");}
    void poll(){
        for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            const auto at=source==n::InventorySource::Namespace?0u:1u;const auto view=service_.capture();
            if(!view->sources[at].outstanding)continue;const auto value=service_.poll(source,0);worker(source,value);
            if(text(value,"status")!="accepted_running")worker(source,service_.retire(source,0));
        }
        if(!outstanding()) {active_=false;note("settled");}
    }
    void timeout(){if(timed_out_)return;timed_out_=true;for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
        const auto at=source==n::InventorySource::Namespace?0u:1u;if(service_.capture()->sources[at].outstanding)service_.timeout(source);}
        note("timeout");}
public:
    V workers=V::array(),events=V::array(),trace=V::array(),errors=V::array(),model_samples=V::array();unsigned pulses=0;
    Driver(n::InventorySession& service,const V& stages,Controls& controls):service_(service),stages_(stages),controls_(controls){}
    void initial(){start();release();const auto until=GetTickCount64()+5000;
        while(active_ && GetTickCount64()<until){poll();if(active_)Sleep(5);}require(!active_,"fixture_initial_outstanding");
        service_.publish();for(const auto& source:service_.capture()->sources)require(source.state==disked::SourceState::Complete,"fixture_initial_incomplete");}
    void retain(disked::FrontendSession& frontend,const std::string& label){
        const auto publication=service_.port().publication();if(!publications_.empty() && publication==publications_.back())return;
        if(trace.items.size()==32)throw std::length_error("fixture_publication_trace_limit");const auto snapshot=frontend.snapshot();
        auto value=publication_value(publication,snapshot);value.put("label",V::string(label)).put("stage",V::string(std::to_string(stage_)))
            .put("selection",frontend.selection());trace.items.push_back(std::move(value));publications_.push_back(publication);snapshots_.push_back(snapshot);
    }
    void pulse(disked::FrontendSession& frontend,const std::function<V()>& model){
        ++pulses;
        if(model && (model_samples.items.empty() || text(model(),"view_revision")!=text(model_samples.items.back(),"view_revision"))){
            if(model_samples.items.size()==32)throw std::length_error("fixture_model_trace_limit");model_samples.items.push_back(model());}
        try {
            if(controls_.signalled(0)){
                if(model){if(model_samples.items.size()==32)throw std::length_error("fixture_model_trace_limit");model_samples.items.push_back(model());}
                if(active_ || outstanding())note("advance_refused_outstanding");
                else if(stage_+1==stages_.items.size())note("advance_refused_exhausted");
                else {++stage_;service_.next_capture();start();}
            }
            if(controls_.signalled(1) && active_ && !released_)release();
            if(controls_.signalled(2) && active_){for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage})service_.cancel(source);note("cancel");}
            if(controls_.signalled(3) && active_)timeout();
            if(active_ && !failed_)poll();
            if(active_ && GetTickCount64()-started_>=5000){timeout();
                for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
                    const auto at=source==n::InventorySource::Namespace?0u:1u;
                    if(service_.capture()->sources[at].outstanding)worker(source,service_.retire(source,0));}
                if(!outstanding()){active_=false;note("deadline_retired");}}
            service_.publish();retain(frontend,"pulse");
        }catch(const std::exception& error){if(errors.items.size()==16)throw;
            errors.items.push_back(V::object().put("stage",V::string(std::to_string(stage_))).put("reason",V::string(error.what())));failed_=true;}
    }
    V cleanup(disked::FrontendSession& frontend){
        auto before=V::array();for(const auto& source:service_.capture()->sources)before.items.push_back(V::boolean_value(source.outstanding));
        for(const auto source:{n::InventorySource::Namespace,n::InventorySource::Storage}){
            const auto at=source==n::InventorySource::Namespace?0u:1u;if(!service_.capture()->sources[at].outstanding)continue;
            service_.cancel(source);service_.release(source);worker(source,service_.retire(source,2000));}
        service_.publish();retain(frontend,"after-renderer-retirement");
        return V::object().put("before",before).put("outstanding",V::boolean_value(outstanding()));
    }
    V retained()const{auto values=V::array();for(std::size_t i=0;i<publications_.size();++i){
        const auto owner=snapshots_[i]->observation_owner();const auto publication=publications_[i];
        const bool matching=owner && owner.get()==&publication->view()->graph && !owner.owner_before(publication) && !publication.owner_before(owner);
        auto value=publication_value(publication,snapshots_[i]);value.put("same_snapshot",V::boolean_value(matching));values.items.push_back(std::move(value));}
        return values;}
};
int render(const V& input,const std::wstring& mode,const wchar_t* output,const disked::WindowsMemoryBudget& budget){
    const auto& reg=field(input,"registry");disked::Registry registry{field(reg,"commands"),field(reg,"syntax"),field(reg,"schemas")};
    const auto composition=text(input,"composition");if(composition!="metadata" && composition!="identity-frame" && composition!="identity")throw std::invalid_argument("fixture_composition");
    const auto style=input.find("terminal_style")?text(input,"terminal_style"):"linear";
    const auto fault=input.find("callback_fault")?text(input,"callback_fault"):"none";
    const auto deferred=input.find("deferred_completion")?text(input,"deferred_completion"):"none";
    if(style!="linear" && style!="screen")throw std::invalid_argument("fixture_terminal_style");
    if(fault!="none" && fault!="pending")throw std::invalid_argument("fixture_callback_fault");
    if(deferred!="none" && deferred!="inspect")throw std::invalid_argument("fixture_deferred_completion");
    if((deferred=="inspect")!=(input.find("completion_control")!=nullptr))throw std::invalid_argument("fixture_completion_control");
    if(deferred=="inspect" && fault!="none")throw std::invalid_argument("fixture_completion_conflict");
    const auto& stages=field(input,"stages");if(stages.kind!=V::Kind::array || stages.items.empty() || stages.items.size()>3)throw std::invalid_argument("fixture_stages");
    if(registry.commands.kind!=V::Kind::array || registry.syntax.kind!=V::Kind::object || registry.parameter_schemas.kind!=V::Kind::object)throw std::invalid_argument("fixture_registry");
    for(const auto& stage:stages.items)if(field(stage,"namespace").kind!=V::Kind::object || field(stage,"storage").kind!=V::Kind::object)throw std::invalid_argument("fixture_stages");
    Controls controls(field(input,"controls"),input.find("completion_control"));ReceiptFile receipt(output);
    auto service=composition=="metadata"?std::unique_ptr<n::InventorySession>(new n::InventorySession()):
        std::unique_ptr<n::InventorySession>(new n::InventorySession(n::StorageFrameProfile::IdentityLayout,
            composition=="identity"?n::StorageGraphProjection::Identity:n::StorageGraphProjection::Frame));
    Driver driver(*service,stages,controls);driver.initial();const auto port=service->port();unsigned callbacks=0,health_calls=0;
    disked::FrontendSession frontend(registry,*port.graph(),[port,&callbacks](){++callbacks;return port.graph();},
        [&](const std::string& id,const V&,const std::string&,const V&){++health_calls;return disked::completed(id,V::object());},disked::FrontendProfile::CachedObservations);
    frontend.refresh_observations();driver.retain(frontend,"initial");auto commands=registry.commands;
    for(auto& command:commands.items)command.put("availability",V::string(disked::FrontendSession::handles(text(command,"id"))?"available":"unavailable"));
    const auto discovery=V::object().put("commands",commands);std::function<V()> state;V final_model,dispatches=V::array();
    bool queued=false,delivered=false;unsigned completion_polls=0;disked::Outcome withheld;V completion_binding;
    const auto dispatch=[&](const std::string& id,const std::string& command,const V& parameters,const std::string& revision)->disked::Submission{
        if(deferred=="inspect" && command=="target.inspect" && completion_binding.kind!=V::Kind::null)throw std::runtime_error("fixture_completion_limit");
        auto value=frontend.dispatch(id,command,parameters,revision);if(dispatches.items.size()==32)throw std::length_error("fixture_dispatch_limit");
        dispatches.items.push_back(V::object().put("request_id",V::string(id)).put("command",V::string(command)).put("parameters",parameters)
            .put("expected_revision",V::string(revision)).put("outcome",value.response));
        if(deferred=="inspect" && command=="target.inspect" && !value.exit_code){
            require(disked::validate_response(value.response).empty(),"fixture_completion_response");
            completion_binding=dispatches.items.back();withheld=value;queued=true;return disked::Submission::deferred();
        }return value;};
    const auto completion_poll=[&](disked::Outcome& value){
        ++completion_polls;if(!queued || !controls.completion_ready())return false;
        value=withheld;queued=false;delivered=true;return true;
    };
    bool callback_threw=false;V callback_sources=V::array();
    const auto advance=[&](){
        driver.pulse(frontend,state);
        if(fault=="pending") {
            const auto capture=service->capture();
            if(std::any_of(capture->sources.begin(),capture->sources.end(),[](const disked::CaptureSource& source){return source.outstanding;})) {
                for(const auto& source:capture->sources)callback_sources.items.push_back(V::boolean_value(source.outstanding));
                callback_threw=true;throw std::runtime_error("fixture_application_callback");
            }
        }
    };const auto before_release=[&](){final_model=state();};int exit=0;
    const disked::CompletionPoll selected_poll=deferred=="inspect"?disked::CompletionPoll(completion_poll):disked::CompletionPoll{};
    if(mode==L"gui")exit=disked::run_windows_gui([&](const V&){auto model=std::unique_ptr<disked::GuiModel>(new disked::GuiModel(frontend,registry,discovery,dispatch,selected_poll));
        auto pointer=model.get();state=[pointer](){return pointer->state();};return model;},advance,before_release);
    else if(mode==L"tui")exit=disked::run_windows_tui(style,[&](){auto model=std::unique_ptr<disked::TuiModel>(new disked::TuiModel(frontend,registry,discovery,dispatch,selected_poll));
        auto pointer=model.get();state=[pointer](){return pointer->state();};return model;},advance,before_release);
    else exit=disked::run_windows_shell(style,[&](){auto model=std::unique_ptr<disked::ShellModel>(new disked::ShellModel(frontend,registry,discovery,dispatch,false,selected_poll));
        auto pointer=model.get();state=[pointer](){return pointer->state();};return model;},advance,before_release);
    state={};const auto retirement=driver.cleanup(frontend);service.reset();
    receipt.write(V::object().put("renderer_exit",V::string(std::to_string(exit))).put("composition",V::string(composition))
        .put("terminal_style",V::string(style)).put("callback_fault",V::string(fault)).put("callback_threw",V::boolean_value(callback_threw))
        .put("callback_sources_before_throw",callback_sources)
        .put("deferred_completion",V::string(deferred)).put("completion_binding",completion_binding)
        .put("completion_queued",V::boolean_value(queued)).put("completion_delivered",V::boolean_value(delivered))
        .put("completion_polls",V::string(std::to_string(completion_polls)))
        .put("trace",driver.trace).put("workers",driver.workers).put("events",driver.events).put("errors",driver.errors).put("model_samples",driver.model_samples)
        .put("final_model_state",final_model).put("dispatches",dispatches).put("retirement",retirement).put("selection",frontend.selection())
        .put("retained_after_session_and_renderer",driver.retained()).put("callbacks",V::string(std::to_string(callbacks)))
        .put("advance_calls",V::string(std::to_string(driver.pulses))).put("health_calls",V::string(std::to_string(health_calls)))
        .put("namespace_api_calls",V::string(std::to_string(disked::nt_fixture::call_count()))).put("storage_api_calls",V::string(std::to_string(disked::nt_storage_fixture::call_count())))
        .put("pointer_bytes",V::string(std::to_string(sizeof(void*)))).put("frontend_budget_ready",V::boolean_value(budget.ready())));
    return exit;
}
}
int wmain(int argc,wchar_t** argv){
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_identity_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);},n::StorageFrameProfile::IdentityLayout);
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_storage_fixture_worker")return n::storage_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_storage_fixture::api(v,notify);});
    if(argc>1 && std::wstring(argv[1])==L"__disked_nt_namespace_fixture_worker")return n::namespace_worker_role(argc,argv,[](const V& v,const std::function<void()>& notify){return disked::nt_fixture::api(v,notify);});
    if(argc!=5 || std::wstring(argv[1])!=L"__disked_nt_inventory_advance_fixture")return 2;
    const auto mode=std::wstring(argv[2]);if(mode!=L"gui" && mode!=L"tui" && mode!=L"shell")return 2;
    disked::WindowsMemoryBudget budget;if(!budget.ready())return 7;
    try{fixture_path(argv[3]);fixture_path(argv[4]);return render(read(argv[3]),mode,argv[4],budget);}
    catch(const std::exception& error){print(V::object().put("status",V::string("refused")).put("reason",V::string(error.what()))
        .put("reader_starts",V::string(std::to_string(reader_starts))));return 3;}
}
