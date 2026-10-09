#include "verification_commands.h"
#include "verification_worker.h"
#include "verification_observation.h"
#include "bootstrap_registry.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* k) {const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_verification_worker")==0)return disked::run_verification_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>4194304)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        auto limits=disked::verification_operation::definition_limits();limits.bytes=4194304;limits.string_bytes=3145728;limits.values=262144;
        const auto v=disked::json::parse(input,limits);const auto mode=text(v,"mode");
        const disked::Registry registry{disked::json::parse(bootstrap::command_catalog_json),disked::json::parse(bootstrap::syntax_json),disked::json::parse(bootstrap::parameter_schemas_json)};
        if(mode=="watch-reader") {
            const auto& header=get(v,"header");const auto p=v.find("snapshot");
            disked::WatchReader reader(text(header,"operation_id"),v.find("worker_epoch")?text(v,"worker_epoch"):"",v.find("sequence")?text(v,"sequence"):"0",v.find("digest")?text(v,"digest"):std::string(64,'0'),p && p->boolean,disked::verification_watch_profile(header));
            auto rows=V::array();for(const auto& event:get(v,"events").items) {auto row=V::object();
                try {row.put("accepted",V::boolean_value(reader.accept(event))).put("error",V::string("")).put("preserved",event);}catch(const std::exception& e) {row.put("error",V::string(e.what()));}
                row.put("sequence",V::string(reader.sequence())).put("digest",V::string(reader.digest()));rows.items.push_back(row);
            }
            std::puts(disked::json::dump(V::object().put("results",rows),limits).c_str());return 0;
        }
        auto ports=disked::verification_actions();unsigned prepare_calls=0,execute_calls=0;
        if(mode=="audit") {
            ports.prepare=[&](const V&) {++prepare_calls;if(v.find("throw"))throw std::runtime_error("owned_port_failure");return get(v,"reply");};
            ports.execute=[&](const V&,const V& g) {++execute_calls;
                if(v.find("expected_grant") && disked::json::dump(g)!=disked::json::dump(get(v,"expected_grant")))throw std::runtime_error("grant_mismatch");
                if(v.find("throw"))throw std::runtime_error("owned_port_failure");return get(v,"reply");};if(v.find("no_ports"))ports={};
        }
        disked::Outcome out;std::shared_ptr<disked::WatchQueue> queue;
        if(mode=="event-request" || mode=="closed-event-request") {queue=std::make_shared<disked::WatchQueue>();if(mode=="closed-event-request")queue->close();}
        if(mode=="request" || mode=="audit" || queue)out=disked::process_request(registry,disked::json::dump(get(v,"request"),limits),
            [&](const std::string& id,const std::string& command,const V& p,const std::string&) {return command=="image.verify"?disked::dispatch_verification(registry,id,p,ports):disked::dispatch_verification_operation(id,command,p);},
            queue?disked::Handler{[queue](const std::string& id,const std::string&,const V& p,const std::string&) {return disked::watch_verification_operation(id,p,queue);}}:disked::Handler{});
        else if(mode=="cli") {
            std::vector<std::string> args;for(const auto& s:get(v,"argv").items) {if(s.kind!=V::Kind::string)throw std::runtime_error("probe_input");args.push_back(s.text);}
            const auto parsed=disked::parse_invocation(registry,args);
            if(!parsed.valid())out=disked::refused("cli",get(parsed.diagnostics.items.front(),"code").text);
            else if(parsed.help_requested)out=disked::completed("cli",parsed.normalized());
            else if(parsed.command_id=="image.verify")out=disked::dispatch_verification(registry,"cli",parsed.parameters,ports);
            else out=disked::dispatch_verification_operation("cli",parsed.command_id,parsed.parameters);
        }else if(mode=="form") {
            V typed;const auto error=disked::form_parameters(registry,*registry.command("image.verify"),get(v,"editor"),typed);
            out=error.empty()?disked::dispatch_verification(registry,"form",typed,ports):disked::refused("form",error);
        }else if(mode=="observe-reply")out=disked::verification_observation("probe",get(v,"reply"));
        else if(mode=="inspect" || mode=="cancel")out=disked::verification_observation("probe",disked::observe_verification_worker(text(v,"operation_id"),text(v,"state_directory"),mode=="cancel"));
        else if(mode=="watch")out=disked::watch_verification_operation("probe",get(v,"parameters"));
        else throw std::runtime_error("probe_input");
        if(!disked::validate_response(out.response).empty() || disked::response_exit(out.response)!=out.exit_code)throw std::runtime_error("probe_response_exit");
        if(mode=="audit")out.response=V::object().put("response",out.response).put("prepare_calls",V::number(std::to_string(prepare_calls))).put("execute_calls",V::number(std::to_string(execute_calls)));
        if(queue) {auto events=V::array();V event;while(queue->pop(event))events.items.push_back(event);queue->close();std::puts(disked::json::dump(V::object().put("response",out.response).put("events",events),limits).c_str());return out.exit_code;}
        if(mode=="audit")std::puts(disked::json::dump(out.response,limits).c_str());else std::fputs(disked::response_frame(out.response).c_str(),stdout);return out.exit_code;
    }catch(const std::exception& e) {std::puts(disked::json::dump(V::object().put("refusal",V::string(e.what()))).c_str());return 99;}
}
