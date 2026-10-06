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
#include <cstdio>

namespace disked {
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
    out.put("reason",Value::string(available?(fake_worker_command(command.find("id")->text)?"fake_operation_subset":"synchronous_native_subset"):"not_implemented"));return out;
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
    if(command=="mode.explain")return completed(request,explain_invocation(host,inputs));
    if(fake_worker_command(command))return dispatch_fake_worker(request,command,parameters);
    if(FrontendSession::handles(command)) {
        if(!session)session.reset(new FrontendSession(command_registry(),fake_graph()));
        return session->dispatch(request,command,parameters,revision);
    }
    return refused(request,"command_unavailable",3);
}
bool human(const Outcome& outcome,const ParseResult& parsed,const InvocationHost& host) {
    if(fake_worker_command(parsed.command_id) && parsed.kind!="help" && outcome.response.find("result")->kind!=Value::Kind::null) {
        if(!host.output_usable)return false;
        std::puts(presentation_json(outcome.response).c_str());
        return std::fflush(stdout)==0 && !std::ferror(stdout);
    }
    if(outcome.exit_code) {
        if(!host.error_usable)return false;
        for(const auto& d:outcome.response.find("diagnostics")->items)
            std::fprintf(stderr,"disked: %s\n",d.find("code")->text.c_str());
        return std::fflush(stderr)==0 && !std::ferror(stderr);
    }
    if(!host.output_usable)return false;
    const auto& value=*outcome.response.find("result");
    if(FrontendSession::handles(parsed.command_id) && parsed.kind!="help")std::puts(presentation_json(value).c_str());
    else if(parsed.command_id=="mode.explain" && parsed.kind!="help")std::puts(json::dump(value).c_str());
    else if(parsed.command_id=="build.inspect" && parsed.kind!="help") {
        for(const auto& pair:value.fields)std::printf("%s=%s\n",pair.first.c_str(),pair.second.text.c_str());
    } else {
        if(parsed.kind=="help")std::puts("DiskEd (fake-only native composition)\nUsage: disked <command-form> [operands] [options]");
        std::puts("id\tcontract_status\timplementation_status\tavailability\treason\tcommand\taliases");
        for(const auto& c:value.find("commands")->items) {
            for(const auto* key:{"id","contract_status","implementation_status","availability","reason"})std::printf("%s\t",c.find(key)->text.c_str());
            bool first=true;
            for(const auto& word:c.find("words")->items) {std::printf("%s%s",first?"":" ",word.text.c_str());first=false;}
            std::putchar('\t');first=true;
            for(const auto& alias:c.find("aliases")->items) {std::printf("%s%s",first?"":", ",alias.text.c_str());first=false;}
            std::putchar('\n');
            if(parsed.kind=="help") {
                std::printf("  %s\n",c.find("summary")->text.c_str());
                for(const auto& binding:c.find("argument_bindings")->items) {
                    const auto* option=binding.find("option");
                    std::printf("  %s%s\n",option?(option->text+" ").c_str():"operand: ",binding.find("parameter")->text.c_str());
                }
            }
        }
        if(parsed.kind=="help") {
            std::puts("Global options (may precede, separate or follow command words before --):");
            for(const auto& option:command_registry().syntax.find("global_options")->items) {
                for(const auto& spelling:option.find("spellings")->items)std::printf("  %s",spelling.text.c_str());
                if(const auto* choices=option.find("choices"))for(const auto& choice:choices->items)std::printf(" %s",choice.text.c_str());
                std::putchar('\n');
            }
        }
    }
    return std::fflush(stdout)==0 && !std::ferror(stdout);
}
}
int run_cli(const std::vector<std::string>& arguments,const InvocationHost& host) {
    bool machine=false;
    try {
        const auto& registry=command_registry();const auto parsed=parse_invocation(registry,arguments);
        const auto format=setting(parsed,"format","human");
        machine=!parsed.output_ambiguous && format!="human";
        Value controls=Value::object();for(const auto& pair:parsed.controls)controls.put(pair.first,Value::string(pair.second));
        const auto inputs=invocation_inputs(host,controls,!parsed.command_id.empty());
        const auto selection=route_invocation(inputs);
        std::unique_ptr<FrontendSession> session;
        Outcome outcome;
        if(!parsed.valid()) {
            outcome=refused("cli","invalid_arguments");outcome.response.fields["diagnostics"].items.clear();
            for(const auto& d:parsed.diagnostics.items) {
                auto code=d.find("code")->text;
                if(code=="command_not_found") {code="command_unavailable";outcome.exit_code=3;}
                outcome.response.fields["diagnostics"].items.push_back(diagnostic(code,Value::object().put("token",*d.find("token"))));
            }
        } else if(parsed.help_requested)outcome=completed("cli",discovery(&parsed));
        else if(setting(parsed,"frontend","auto")=="gui") {
            InvocationHost gui_host=host;auto gui_inputs=inputs;
            return run_windows_gui([&](const Value& observed) {
                gui_host.observations.put("gui",observed).put("display",Value::string("available"));
                gui_host.policy.put("display",Value::boolean_value(true));gui_inputs.put("display",Value::boolean_value(true));
                session.reset(new FrontendSession(registry,fake_graph()));
                auto model=std::unique_ptr<GuiModel>(new GuiModel(*session,registry,discovery(),
                    [&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                        return dispatch(id,command,parameters,gui_host,gui_inputs,session,revision);
                    }));
                if(!parsed.command_id.empty())model->stage(parsed.command_id,parsed.parameters);
                return model;
            });
        }
        else if(const auto* error=selection.find("error"))outcome=refused("cli",error->text,error->text=="argument_conflict"?2:3);
        else if(selection.find("frontend")->text=="tui") {
            return run_windows_tui(setting(parsed,"terminal_presentation","auto"),[&]() {
                session.reset(new FrontendSession(registry,fake_graph()));
                auto model=std::unique_ptr<TuiModel>(new TuiModel(*session,registry,discovery(),
                    [&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                        return dispatch(id,command,parameters,host,inputs,session,revision);
                    }));
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
                return serve(stdin,stdout,format=="ndjson",registry,[&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
                    return dispatch(id,command,parameters,host,machine_inputs,session,revision);
                });
            }
        } else outcome=dispatch("cli",parsed.command_id,parsed.parameters,host,inputs,session);
        if(machine) {if(!host.output_usable || !write_response(stdout,outcome.response))return 4;}
        else if(!human(outcome,parsed,host)) {if(host.error_usable)std::fputs("disked: output_error\n",stderr);return 4;}
        return outcome.exit_code;
    } catch(const std::exception&) {
        if(machine && host.output_usable) {try {write_response(stdout,refused("@unparsed","internal_error",4).response);}catch(...) {}}
        else if(!machine && host.error_usable)std::fputs("disked: internal_error\n",stderr);
        return 4;
    }
}
}
