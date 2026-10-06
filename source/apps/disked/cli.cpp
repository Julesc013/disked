#include "cli.h"
#include "command_registry.h"
#include "bootstrap_registry.h"
#include "bootstrap.h"
#include "protocol.h"
#include "session.h"
#include "graph.h"
#include "terminal.h"
#include "gui.h"
#include "fake_worker.h"
#include "output.h"
#include "memory_budget.h"
#include <cstdio>

namespace disked {
#ifdef DISKED_CAPTURE_CAMPAIGN
json::Value capture_campaign_report();
#endif
using json::Value;
namespace {
bool implemented(const std::string& id) {
    for(const auto& c:bootstrap::commands)if(id==c.id)return c.implemented;
    return false;
}
std::string setting(const ParseResult& parsed,const std::string& field,const std::string& fallback) {
    const auto p=parsed.controls.find(field);return p==parsed.controls.end()?fallback:p->second;
}
Value build_information() {
    Value result=Value::object();
#define IDENTITY_FIELD(name) result.put(#name,Value::string(bootstrap::name))
    IDENTITY_FIELD(product);IDENTITY_FIELD(version);IDENTITY_FIELD(source_revision);IDENTITY_FIELD(source_state);
    IDENTITY_FIELD(input_digest);IDENTITY_FIELD(target);IDENTITY_FIELD(composition);IDENTITY_FIELD(compiler);
    IDENTITY_FIELD(sdk);IDENTITY_FIELD(configuration);IDENTITY_FIELD(language);IDENTITY_FIELD(crt);IDENTITY_FIELD(configuration_digest);
#undef IDENTITY_FIELD
    return result.put("fake_provider",Value::string(fake_provider_identity()));
}
Value command_description(const Value& command) {
    Value out=command;const bool available=implemented(command.find("id")->text);
    out.put("contract_status",*command.find("availability"));
    out.put("implementation_status",Value::string(available?"implemented":"planned"));
    out.put("availability",Value::string(available?"available":"unavailable"));
    const auto id=command.find("id")->text;
    out.put("reason",Value::string(!available?"not_implemented":id=="shell.open"?"interactive_console_required":
        id=="shell.close"?"shell_session_only":fake_worker_command(id)?"fake_operation_subset":"synchronous_native_subset"));return out;
}
Value discovery(const ParseResult* help=nullptr) {
    Value result=Value::object(),commands=Value::array();
    for(const auto& command:command_registry().commands.items) {
        if(help && !help->command_id.empty() && command.find("id")->text!=help->command_id)continue;
        if(help && !help->domain.empty() && help->domain!="@root" && command.find("words")->items.front().text!=help->domain)continue;
        commands.items.push_back(command_description(command));
    }
    result.put("commands",commands);
    if(help)result.put("usage",Value::string("disked <command-form> [operands] [options]"))
        .put("scope",Value::string(!help->command_id.empty()?help->command_id:help->domain))
        .put("global_options",*command_registry().syntax.find("global_options"));
    return result;
}
Outcome dispatch(const std::string& request,const std::string& command,const Value& parameters,const InvocationHost& host,const Value& inputs,
    std::unique_ptr<FrontendSession>& session,const std::string& revision="") {
    if(!implemented(command))return refused(request,"command_unavailable",3);
    if(command=="build.inspect")return completed(request,build_information());
    if(command=="command.list")return completed(request,discovery());
    if(command=="mode.explain") {
        auto value=explain_invocation(host,inputs);
#ifdef DISKED_CAPTURE_CAMPAIGN
        value.put("test_capture_campaign",capture_campaign_report());
#endif
        return completed(request,std::move(value));
    }
    if(command=="shell.open")return refused(request,"interactive_session_requires_terminal",3);
    if(command=="shell.close")return refused(request,"command_requires_shell",3);
    if(fake_worker_command(command))return dispatch_fake_worker(request,command,parameters);
    if(FrontendSession::handles(command)) {
        if(!session)session=make_fake_session(command_registry());
        return session->dispatch(request,command,parameters,revision);
    }
    return refused(request,"command_unavailable",3);
}
Submission frontend_dispatch(const std::string& request,const std::string& command,const Value& parameters,
    const InvocationHost& host,const Value& inputs,std::unique_ptr<FrontendSession>& session,
    RequestChannel& channel,const std::string& revision) {
    if(implemented(command) && fake_worker_command(command)) {
        // The background callback owns only immutable request data. It never
        // captures the frontend/session or performs UI work after disconnection.
        return channel.submit(request,[request,command,parameters]() {return dispatch_fake_worker(request,command,parameters);});
    }
    return dispatch(request,command,parameters,host,inputs,session,revision);
}
Outcome bounded_dispatch(const std::string& request,const std::string& command,const Value& parameters,
    const InvocationHost& host,const Value& inputs,std::unique_ptr<FrontendSession>& session,
    std::unique_ptr<BoundedRequests>& calls,const std::string& revision="") {
    if(implemented(command) && fake_worker_command(command)) {
        if(!calls)calls.reset(new BoundedRequests());
        auto expired=completed(request,Value::object().put("request_state",Value::string("unresolved"))
            .put("state_directory",*parameters.find("state_directory")));
        expired.exit_code=6;expired.response.put("status",Value::string("unknown"));
        if(const auto* operation=parameters.find("operation_id"))expired.response.put("operation_id",*operation);
        expired.response.fields["diagnostics"].items.push_back(diagnostic("request_wait_expired"));
        return calls->run(request,[request,command,parameters]() {return dispatch_fake_worker(request,command,parameters);},
            std::move(expired),std::chrono::milliseconds(4000));
    }
    return dispatch(request,command,parameters,host,inputs,session,revision);
}
Outcome stream_watch(const std::string& request,const Value& parameters,std::unique_ptr<BoundedRequests>& calls,const ResponseSink& output) {
    if(!calls)calls.reset(new BoundedRequests());
    const auto queue=std::make_shared<WatchQueue>();
    struct Close {std::shared_ptr<WatchQueue> queue;~Close() {queue->close();}} close{queue};
    auto expired=completed(request,Value::object().put("request_state",Value::string("unresolved"))
        .put("state_directory",*parameters.find("state_directory")));
    expired.exit_code=6;expired.response.put("status",Value::string("unknown")).put("operation_id",*parameters.find("operation_id"));
    expired.response.fields["diagnostics"].items.push_back(diagnostic("request_wait_expired"));
    return calls->run(request,[request,parameters,queue]() {return watch_fake_worker(request,parameters,queue);},std::move(expired),
        std::chrono::milliseconds(4000),[&]() {Value event;while(queue->pop(event))if(!output(event))return false;return true;});
}
bool human(const Outcome& outcome,const ParseResult& parsed,const InvocationHost& host,WindowsOutput& output,WindowsOutput& errors) {
    if(fake_worker_command(parsed.command_id) && parsed.kind!="help" && outcome.response.find("result")->kind!=Value::Kind::null)
        return host.output_usable && output.write(presentation_json(outcome.response)+"\n");
    if(outcome.exit_code) {
        if(!host.error_usable)return false;
        std::string text;for(const auto& d:outcome.response.find("diagnostics")->items)text+="disked: "+d.find("code")->text+"\n";
        return errors.write(std::move(text));
    }
    if(!host.output_usable)return false;
    const auto& value=*outcome.response.find("result");std::string text;
    if(FrontendSession::handles(parsed.command_id) && parsed.kind!="help")text=presentation_json(value)+"\n";
    else if(parsed.command_id=="mode.explain" && parsed.kind!="help")text=json::dump(value)+"\n";
    else if(parsed.command_id=="build.inspect" && parsed.kind!="help") {
        for(const auto& pair:value.fields)text+=pair.first+"="+pair.second.text+"\n";
    } else {
        if(parsed.kind=="help")text+="DiskEd (fake-only native composition)\nUsage: disked <command-form> [operands] [options]\n";
        text+="id\tcontract_status\timplementation_status\tavailability\treason\tcommand\taliases\n";
        for(const auto& c:value.find("commands")->items) {
            for(const auto* key:{"id","contract_status","implementation_status","availability","reason"})text+=c.find(key)->text+"\t";
            bool first=true;
            for(const auto& word:c.find("words")->items) {text+=(first?"":" ")+word.text;first=false;}
            text+='\t';first=true;
            for(const auto& alias:c.find("aliases")->items) {text+=(first?"":", ")+alias.text;first=false;}
            text+='\n';
            if(parsed.kind=="help") {
                text+="  "+c.find("summary")->text+"\n";
                for(const auto& binding:c.find("argument_bindings")->items) {
                    const auto* option=binding.find("option");
                    text+="  "+(option?option->text+" ":"operand: ")+binding.find("parameter")->text+"\n";
                }
            }
        }
        if(parsed.kind=="help") {
            text+="Global options (may precede, separate or follow command words before --):\n";
            for(const auto& option:command_registry().syntax.find("global_options")->items) {
                for(const auto& spelling:option.find("spellings")->items)text+="  "+spelling.text;
                if(const auto* choices=option.find("choices"))for(const auto& choice:choices->items)text+=" "+choice.text;
                text+='\n';
            }
        }
    }
    return output.write(std::move(text));
}
}
int run_cli(const std::vector<std::string>& arguments,const InvocationHost& host) {
    bool machine=false;WindowsOutput output(stdout),errors(stderr);
    auto emit=[&](const Value& value) {return output.write(response_frame(value));};
    try {
        const auto& registry=command_registry();const auto parsed=parse_invocation(registry,arguments);
        const auto format=setting(parsed,"format","human");
        machine=!parsed.output_ambiguous && format!="human";
        Value controls=Value::object();for(const auto& pair:parsed.controls)controls.put(pair.first,Value::string(pair.second));
        const auto inputs=invocation_inputs(host,controls,!parsed.command_id.empty());
        const auto selection=route_invocation(inputs);
        std::unique_ptr<FrontendSession> session;
        std::unique_ptr<RequestChannel> channel;
        std::unique_ptr<BoundedRequests> calls;
        std::unique_ptr<WindowsMemoryBudget> memory;
        if(parsed.valid())memory.reset(new WindowsMemoryBudget());
        Outcome outcome;
        if(!parsed.valid()) {
            outcome=refused("cli","invalid_arguments");outcome.response.fields["diagnostics"].items.clear();
            for(const auto& d:parsed.diagnostics.items) {
                auto code=d.find("code")->text;
                if(code=="command_not_found") {code="command_unavailable";outcome.exit_code=3;}
                outcome.response.fields["diagnostics"].items.push_back(diagnostic(code,Value::object().put("token",*d.find("token"))));
            }
        } else if(!memory->ready()) {
            outcome=refused("cli",memory->error(),3);
            auto& detail=outcome.response.fields["diagnostics"].items.front();
            detail.put("platform_code",Value::string(std::to_string(memory->platform_error())));
            detail.put("parameters",Value::object().put("process_limit_bytes",Value::string(std::to_string(WindowsMemoryBudget::limit_bytes()))));
            if(memory->probe_bytes())detail.fields["parameters"].put("test_allocation_bytes",Value::string(std::to_string(memory->probe_bytes())));
        } else if(parsed.help_requested)outcome=completed("cli",discovery(&parsed));
        else if(parsed.command_id=="shell.open") {
            auto shell_controls=controls;
            shell_controls.put("frontend",Value::string("cli")).put("interactive",Value::string("yes"));
            const auto shell_inputs=invocation_inputs(host,shell_controls,true);
            return run_windows_shell(setting(parsed,"terminal_presentation","auto"),[&]() {
                channel.reset(new RequestChannel());
                session=make_fake_session(registry);
                const auto* history=parsed.parameters.find("history");
                return std::unique_ptr<ShellModel>(new ShellModel(*session,registry,discovery(),
                    [&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                        return frontend_dispatch(id,command,parameters,host,shell_inputs,session,*channel,revision);
                    },history && history->text=="session",[&](Outcome& value) {return channel->poll(value);}));
            });
        }
        else if(setting(parsed,"frontend","auto")=="gui") {
            InvocationHost gui_host=host;auto gui_inputs=inputs;
            return run_windows_gui([&](const Value& observed) {
                channel.reset(new RequestChannel());
                gui_host.observations.put("gui",observed).put("display",Value::string("available"));
                gui_host.policy.put("display",Value::boolean_value(true));gui_inputs.put("display",Value::boolean_value(true));
                session=make_fake_session(registry);
                auto model=std::unique_ptr<GuiModel>(new GuiModel(*session,registry,discovery(),
                    [&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                        return frontend_dispatch(id,command,parameters,gui_host,gui_inputs,session,*channel,revision);
                    },[&](Outcome& value) {return channel->poll(value);}));
                if(!parsed.command_id.empty())model->stage(parsed.command_id,parsed.parameters);
                return model;
            });
        }
        else if(const auto* error=selection.find("error"))outcome=refused("cli",error->text,error->text=="argument_conflict"?2:3);
        else if(selection.find("frontend")->text=="tui") {
            return run_windows_tui(setting(parsed,"terminal_presentation","auto"),[&]() {
                channel.reset(new RequestChannel());
                session=make_fake_session(registry);
                auto model=std::unique_ptr<TuiModel>(new TuiModel(*session,registry,discovery(),
                    [&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                        return frontend_dispatch(id,command,parameters,host,inputs,session,*channel,revision);
                    },[&](Outcome& value) {return channel->poll(value);}));
                if(!parsed.command_id.empty())model->stage(parsed.command_id,parsed.parameters);
                return model;
            });
        }
        else if(parsed.kind=="help")outcome=completed("cli",discovery(&parsed));
        else if(parsed.command_id=="protocol.serve") {
            if(!machine || setting(parsed,"interactive","auto")=="yes")outcome=refused("cli","argument_conflict");
            else if(!host.output_usable)return 4;
            else if(!host.input_usable)outcome=refused("@unparsed","input_error",4);
            else {
                auto machine_inputs=inputs;machine_inputs.put("command",Value::boolean_value(true));
                return serve(stdin,format=="ndjson",registry,[&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                    return bounded_dispatch(id,command,parameters,host,machine_inputs,session,calls,revision);
                },emit,[&](const std::string& id,const std::string&,const Value& parameters,const std::string&) {
                    return stream_watch(id,parameters,calls,emit);
                });
            }
        } else if(parsed.command_id=="operation.watch" && format=="ndjson")outcome=stream_watch("cli",parsed.parameters,calls,emit);
        else outcome=bounded_dispatch("cli",parsed.command_id,parsed.parameters,host,inputs,session,calls);
        if(machine) {if(!host.output_usable || !emit(outcome.response))return 4;}
        else if(!human(outcome,parsed,host,output,errors)) {if(host.error_usable)errors.write("disked: output_error\n");return 4;}
        return outcome.exit_code;
    } catch(const std::exception&) {
        if(machine && host.output_usable) {try {emit(refused("@unparsed","internal_error",4).response);}catch(...) {}}
        else if(!machine && host.error_usable)errors.write("disked: internal_error\n");
        return 4;
    }
}
}
