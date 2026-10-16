#include "policy.h"
#include <algorithm>
#include <initializer_list>
namespace disked {
using json::Value;
namespace {
std::string text(const Value& input,const std::string& key,const std::string& fallback="") {
    const auto* value=input.find(key);return value && value->kind==Value::Kind::string?value->text:fallback;
}
bool boolean(const Value& input,const std::string& key,bool fallback=false) {
    const auto* value=input.find(key);return value && value->kind==Value::Kind::boolean?value->boolean:fallback;
}
bool in(const std::string& value,std::initializer_list<const char*> choices) {
    return std::any_of(choices.begin(),choices.end(),[&](const char* choice){return value==choice;});
}
Value error(const char* code) {return Value::object().put("error",Value::string(code));}
}
Value route_invocation(const Value& input) {
    const auto front=text(input,"frontend","auto"),format=text(input,"format","human"),interaction=text(input,"interactive","auto");
    const auto terminal=text(input,"terminal","none");
    const bool gui=boolean(input,"gui_available"),display=boolean(input,"display"),tui=boolean(input,"tui_available",true);
    auto result=[&](const std::string& mode,bool interactive,const char* reason) {
        return Value::object().put("frontend",Value::string(mode)).put("format",Value::string(format))
            .put("interactive",Value::boolean_value(interactive)).put("reason",Value::string(reason));
    };
    if(!in(front,{"auto","cli","tui","gui","plain"}) || !in(format,{"human","json","ndjson"}) ||
        !in(interaction,{"auto","yes","no"}))return error("invalid_argument");
    if(format!="human") {
        if(in(front,{"gui","tui"}) || interaction=="yes")return error("argument_conflict");
        return result("cli",false,"machine-output");
    }
    if(in(front,{"gui","tui"}) && interaction=="no")return error("argument_conflict");
    const bool default_prompt=terminal!="none" && !in(text(input,"stdin"),{"pipe","file","absent","invalid"}) &&
        !in(text(input,"stdout"),{"pipe","file","absent","invalid"});
    const bool prompt=boolean(input,"prompt_channel",default_prompt);
    if(!in(front,{"gui","tui"}) && interaction=="yes" && !prompt)return error("interaction_unavailable");
    if(front!="auto") {
        if(front=="gui" && !(gui && display))return error("frontend_unavailable");
        if(front=="tui" && (terminal=="none" || !tui))return error("frontend_unavailable");
        return result(front,in(front,{"gui","tui"}) || interaction=="yes","explicit-frontend");
    }
    if(boolean(input,"command"))return result("cli",interaction=="yes","explicit-command");
    if(interaction=="no")return result("cli",false,"noninteractive-request");
    if(interaction=="yes")return result("cli",true,"explicit-interaction");
    if(boolean(input,"desktop") && gui && display)return result("gui",true,"desktop-activation");
    if(in(text(input,"stdin"),{"pipe","file"}) || in(text(input,"stdout"),{"pipe","file"}))return result("cli",false,"redirected-stream");
    if(terminal=="limited")return result("plain",false,"limited-terminal");
    if(terminal=="capable" && text(input,"console_owner")=="caller")
        return tui?result("tui",true,"interactive-terminal"):result("plain",false,"tui-unavailable");
    if(terminal=="capable")return result("plain",false,"ambiguous-launch");
    return result("plain",false,"no-interactive-host");
}
Value invocation_inputs(const InvocationHost& host,const Value& controls,bool command) {
    Value result=host.policy;
    for(const auto* key:{"frontend","format","interactive","terminal_presentation"})if(const auto* value=controls.find(key))result.put(key,*value);
    return result.put("command",Value::boolean_value(command));
}
Value explain_invocation(const InvocationHost& host,const Value& inputs) {
    auto observations=host.observations;
    if(observations.find("terminal_capabilities") && inputs.find("terminal_presentation"))
        observations.fields["terminal_capabilities"].put("prefer_linear",Value::boolean_value(inputs.find("terminal_presentation")->text=="linear"));
    return Value::object().put("observations",observations).put("policy_inputs",inputs)
        .put("selection",route_invocation(inputs)).put("bare_selection",route_invocation(host.policy));
}
}
