#include "commands.h"
#include "acquisition_worker.h"
#include "bootstrap_registry.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* k) {const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_acquisition_worker")==0)return disked::run_acquisition_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>65536)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        const auto v=disked::json::parse(input);const auto mode=text(v,"mode");
        const disked::Registry registry{disked::json::parse(bootstrap::command_catalog_json),disked::json::parse(bootstrap::syntax_json),disked::json::parse(bootstrap::parameter_schemas_json)};
        auto ports=disked::acquisition_actions();
        unsigned prepare_calls=0,execute_calls=0;
        if(mode=="audit") {
            ports.prepare=[&](const V&) {++prepare_calls;return get(v,"reply");};
            ports.execute=[&](const V&,const V&) {
                ++execute_calls;if(v.find("throw"))throw std::runtime_error("controlled_owned_port_failure");return get(v,"reply");
            };
        }
        disked::Outcome out;
        if(mode=="request" || mode=="audit") {
            out=disked::process_request(registry,disked::json::dump(get(v,"request")),[&](const std::string& id,const std::string& command,const V& p,const std::string&) {
                return command=="image.acquire"?disked::dispatch_acquisition(registry,id,p,ports):disked::dispatch_acquisition_operation(id,command,p);
            });
        } else if(mode=="cli") {
            std::vector<std::string> args;for(const auto& s:get(v,"argv").items) {if(s.kind!=V::Kind::string)throw std::runtime_error("probe_input");args.push_back(s.text);}
            const auto parsed=disked::parse_invocation(registry,args);
            if(!parsed.valid())out=disked::refused("cli",parsed.diagnostics.items.front().find("code")->text);
            else if(parsed.help_requested)out=disked::completed("cli",parsed.normalized());
            else if(parsed.command_id!="image.acquire")out=disked::dispatch_acquisition_operation("cli",parsed.command_id,parsed.parameters);
            else out=disked::dispatch_acquisition(registry,"cli",parsed.parameters,ports);
        } else if(mode=="form") {
            V typed;const auto error=disked::form_parameters(registry,*registry.command("image.acquire"),get(v,"editor"),typed);
            out=error.empty()?disked::dispatch_acquisition(registry,"form",typed,ports):disked::refused("form",error);
        } else if(mode=="observe-reply")out=disked::acquisition_observation("probe",get(v,"reply"));
        else if(mode=="inspect" || mode=="cancel")out=disked::acquisition_observation("probe",disked::observe_acquisition_worker(text(v,"operation_id"),text(v,"state_directory"),mode=="cancel"));
        else throw std::runtime_error("probe_input");
        const auto validation=disked::validate_response(out.response);if(!validation.empty())throw std::runtime_error(validation);
        if(mode=="audit")out.response=V::object().put("response",out.response).put("prepare_calls",V::number(std::to_string(prepare_calls)))
            .put("execute_calls",V::number(std::to_string(execute_calls)));
        std::fputs(disked::response_frame(out.response).c_str(),stdout);return out.exit_code;
    } catch(const std::exception& e) {std::puts(disked::json::dump(V::object().put("refusal",V::string(e.what()))).c_str());return 99;}
}
