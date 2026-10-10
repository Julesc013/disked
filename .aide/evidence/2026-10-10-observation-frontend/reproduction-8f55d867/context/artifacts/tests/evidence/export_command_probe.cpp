#include "export_commands.h"
#include "report_worker.h"
#include "bootstrap_registry.h"
#include "report_observation.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* k) {const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
V shape_error(disked::Registry registry,const V& shape,const V& value,const std::string& path,unsigned depth=0) {
    if(depth>32)throw std::runtime_error("probe_shape_depth");
    auto properties=V::object().put("candidate",shape);registry.parameter_schemas.put("urn:probe",V::object().put("type",V::string("object")).put("properties",properties));
    const auto descriptor=V::object().put("syntax_status",V::string("defined")).put("parameter_schema",V::string("urn:probe"));
    const auto error=disked::validate_parameters(registry,descriptor,V::object().put("candidate",value));
    if(error.empty())return V{};
    if(const auto ref=shape.find("$ref"))if(const auto target=registry.parameter_schemas.find(ref->text)) {
        const auto child=shape_error(registry,*target,value,path,depth+1);if(child.kind!=V::Kind::null)return child;
    }
    if(const auto props=shape.find("properties"))for(const auto& pair:props->fields)if(const auto item=value.find(pair.first)) {
        const auto child=shape_error(registry,pair.second,*item,path+"/"+pair.first,depth+1);if(child.kind!=V::Kind::null)return child;
    }
    if(const auto items=shape.find("items"))for(std::size_t i=0;i<value.items.size();++i) {
        const auto child=shape_error(registry,*items,value.items[i],path+"/"+std::to_string(i),depth+1);if(child.kind!=V::Kind::null)return child;
    }
    return V::object().put("path",V::string(path)).put("error",V::string(error));
}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_report_worker")==0)return disked::run_report_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>1048576)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        auto limits=disked::report_operation::definition_limits();limits.bytes=1048576;limits.string_bytes=65536;limits.values=131072;limits.depth=32;
        const auto v=disked::json::parse(input,limits);const auto mode=text(v,"mode");
        const disked::Registry registry{disked::json::parse(bootstrap::command_catalog_json),disked::json::parse(bootstrap::syntax_json),disked::json::parse(bootstrap::parameter_schemas_json)};
        if(mode=="shape-audit") {const auto result=shape_error(registry,*registry.parameter_schemas.find("urn:disked:schema:export-command-parameters:1"),get(v,"parameters"),"");std::puts(disked::json::dump(result).c_str());return 0;}
        if(mode=="watch-reader") {
            const auto& header=get(v,"header");const auto profile=disked::report_watch_profile(header);const auto p=v.find("snapshot");
            disked::WatchReader reader(text(header,"operation_id"),v.find("worker_epoch")?text(v,"worker_epoch"):"",v.find("sequence")?text(v,"sequence"):"0",v.find("digest")?text(v,"digest"):std::string(64,'0'),p && p->boolean,profile);
            auto result=V::array();for(const auto& event:get(v,"events").items) {
                auto row=V::object();try {row.put("accepted",V::boolean_value(reader.accept(event))).put("error",V::string("")).put("preserved",event);}
                catch(const std::exception& error) {row.put("error",V::string(error.what()));}
                row.put("sequence",V::string(reader.sequence())).put("digest",V::string(reader.digest()));result.items.push_back(row);
            }
            std::puts(disked::json::dump(V::object().put("results",result),limits).c_str());return 0;
        }
        if(mode=="watch-queue") {
            disked::WatchQueue queue;unsigned count=0;std::string error;
            const auto repeats=v.find("repeat")?std::stoul(get(v,"repeat").text):1;if(repeats>128)throw std::runtime_error("probe_input");
            try {for(unsigned i=0;i<repeats;++i)for(const auto& event:get(v,"events").items) {if(queue.push(event))++count;if(v.find("pop_each")) {V item;queue.pop(item);}}}
            catch(const std::exception& failure) {error=failure.what();}
            std::puts(disked::json::dump(V::object().put("accepted",V::number(std::to_string(count))).put("error",V::string(error))).c_str());return 0;
        }
        auto ports=disked::export_actions();
        unsigned prepare_calls=0,execute_calls=0;
        if(mode=="audit") {
            ports.prepare=[&](const V&) {++prepare_calls;if(v.find("throw"))throw std::runtime_error("owned_port_failure");return get(v,"reply");};
            ports.execute=[&](const V&,const V& grant) {
                ++execute_calls;if(v.find("expected_grant") && disked::json::dump(grant)!=disked::json::dump(get(v,"expected_grant")))throw std::runtime_error("grant_mismatch");
                if(v.find("throw"))throw std::runtime_error("owned_port_failure");return get(v,"reply");
            };
            if(v.find("no_ports"))ports={};
        }
        disked::Outcome out;
        std::shared_ptr<disked::WatchQueue> queue;
        if(mode=="event-request" || mode=="closed-event-request") {queue=std::make_shared<disked::WatchQueue>();if(mode=="closed-event-request")queue->close();}
        if(mode=="request" || mode=="audit" || mode=="event-request" || mode=="closed-event-request")out=disked::process_request(registry,disked::json::dump(get(v,"request"),limits),
            [&](const std::string& id,const std::string& command,const V& p,const std::string&) {return command=="evidence.export"?disked::dispatch_export(registry,id,p,ports):disked::dispatch_report_operation(id,command,p);},
            queue?disked::Handler{[queue](const std::string& id,const std::string&,const V& p,const std::string&) {return disked::watch_report_worker(id,p,queue);}}:disked::Handler{});
        else if(mode=="cli") {
            std::vector<std::string> args;for(const auto& s:get(v,"argv").items) {if(s.kind!=V::Kind::string)throw std::runtime_error("probe_input");args.push_back(s.text);}
            const auto parsed=disked::parse_invocation(registry,args);
            if(!parsed.valid())out=disked::refused("cli",parsed.diagnostics.items.front().find("code")->text);
            else if(parsed.help_requested)out=disked::completed("cli",parsed.normalized());
            else if(parsed.command_id!="evidence.export")out=disked::dispatch_report_operation("cli",parsed.command_id,parsed.parameters);
            else out=disked::dispatch_export(registry,"cli",parsed.parameters,ports);
        } else if(mode=="form") {
            V typed;const auto error=disked::form_parameters(registry,*registry.command("evidence.export"),get(v,"editor"),typed);
            out=error.empty()?disked::dispatch_export(registry,"form",typed,ports):disked::refused("form",error);
        } else if(mode=="observe-reply")out=disked::export_observation("probe",get(v,"reply"));
        else if(mode=="inspect" || mode=="cancel")out=disked::export_observation("probe",disked::observe_report_worker(text(v,"operation_id"),text(v,"state_directory"),mode=="cancel"));
        else if(mode=="watch")out=disked::watch_report_worker("probe",get(v,"parameters"));
        else throw std::runtime_error("probe_input");
        const auto validation=disked::validate_response(out.response);if(!validation.empty() || disked::response_exit(out.response)!=out.exit_code)throw std::runtime_error("probe_response_exit");
        if(mode=="audit")out.response=V::object().put("response",out.response).put("prepare_calls",V::number(std::to_string(prepare_calls))).put("execute_calls",V::number(std::to_string(execute_calls)));
        if(queue) {auto events=V::array();V event;while(queue->pop(event))events.items.push_back(event);queue->close();std::puts(disked::json::dump(V::object().put("response",out.response).put("events",events),limits).c_str());return out.exit_code;}
        std::fputs(disked::response_frame(out.response).c_str(),stdout);return out.exit_code;
    } catch(const std::exception& e) {std::puts(disked::json::dump(V::object().put("refusal",V::string(e.what()))).c_str());return 99;}
}
