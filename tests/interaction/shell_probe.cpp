#include "shell_model.h"
#include "command_registry.h"
#include "bootstrap_registry.h"
#include "graph.h"
#include "health_observer.h"
#include <iostream>
#include <memory>
using disked::json::Value;
int main(int argc,char**) {
    auto registry=disked::command_registry();auto graph=disked::fake_graph();disked::FrontendSession session(registry,graph,{},disked::fake_health_observation);
    auto commands=registry.commands;for(auto& c:commands.items) {
        bool available=false;for(const auto& row:bootstrap::commands)if(c.find("id")->text==row.id)available=row.implemented;
        if(argc==2 && c.find("id")->text=="image.acquire")available=true;
        c.put("availability",Value::string(available?"available":"unavailable"));
    }
    auto discovery=Value::object().put("commands",commands);Value calls=Value::array();bool large=false;
    disked::Handler handler=[&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
        calls.items.push_back(Value::object().put("command",Value::string(command)).put("parameters",parameters).put("revision",Value::string(revision)));
        if(large) {
            auto value=Value::array();for(unsigned i=0;i<64;++i)value.items.push_back(Value::string(std::string(4000,'x')));
            return disked::completed(id,value);
        }
        if(disked::FrontendSession::handles(command))return session.dispatch(id,command,parameters,revision);
        auto result=Value::object().put("test_static",Value::string(command));
        if(command=="image.acquire")result.put("test_parameters",parameters);
        return disked::completed(id,result);
    };
    std::unique_ptr<disked::ShellModel> model(new disked::ShellModel(session,registry,discovery,handler,false));
    const std::map<std::string,disked::TuiKey> keys={
        {"text",disked::TuiKey::Text},{"up",disked::TuiKey::Up},{"down",disked::TuiKey::Down},{"left",disked::TuiKey::Left},{"right",disked::TuiKey::Right},
        {"home",disked::TuiKey::Home},{"end",disked::TuiKey::End},{"delete",disked::TuiKey::Delete},{"backspace",disked::TuiKey::Backspace},
        {"enter",disked::TuiKey::Enter},{"tab",disked::TuiKey::Tab},{"escape",disked::TuiKey::Escape},{"f9",disked::TuiKey::F9},
        {"f2",disked::TuiKey::F2},{"f3",disked::TuiKey::F3},{"f4",disked::TuiKey::F4},{"f5",disked::TuiKey::F5},{"f6",disked::TuiKey::F6},{"f10",disked::TuiKey::F10},
        {"pageup",disked::TuiKey::PageUp},{"pagedown",disked::TuiKey::PageDown}};
    std::string line;std::uint64_t linear=0;
    while(std::getline(std::cin,line))try {
        disked::json::Limits input_limits;input_limits.bytes=262144;input_limits.string_bytes=65537;
        const auto input=disked::json::parse(line,input_limits);const auto op=input.find("op")->text;Value result;
        if(op=="lex") {
            const auto value=disked::tokenize_shell(input.find("line")->text);auto tokens=Value::array();
            for(const auto& t:value.tokens)tokens.items.push_back(Value::object().put("value",Value::string(t.value)).put("begin",Value::number(std::to_string(t.begin))).put("end",Value::number(std::to_string(t.end))));
            result=Value::object().put("tokens",tokens).put("error",Value::string(value.error)).put("byte",Value::number(std::to_string(value.error_byte)));
        } else if(op=="quote")result=Value::string(disked::quote_shell(input.find("value")->text));
        else if(op=="reset") {
            calls=Value::array();linear=0;large=input.find("large") && input.find("large")->boolean;
            if(const auto* secret=input.find("secret"))registry.parameter_schemas.fields["urn:disked:schema:command-target-parameters:1"].fields["properties"].fields["target_id"].put("writeOnly",*secret);
            model.reset(new disked::ShellModel(session,registry,discovery,handler,input.find("history") && input.find("history")->boolean));result=model->state();
        } else if(op=="key") {
            const auto* text=input.find("text"),*repeat=input.find("repeat");
            model->input({keys.at(input.find("key")->text),text?text->text:"",repeat && repeat->boolean});result=model->state();
        } else if(op=="state")result=model->state();
        else if(op=="calls")result=calls;
        else if(op=="publish") {session.publish(graph);result=session.snapshot()->value();}
        else if(op=="linear") {result=Value::array();for(const auto& s:model->linear_records(linear))result.items.push_back(Value::string(s));}
        else if(op=="render") {
            result=Value::array();for(const auto& s:model->render(static_cast<unsigned>(std::stoul(input.find("columns")->text)),
                static_cast<unsigned>(std::stoul(input.find("rows")->text)),false))result.items.push_back(Value::string(s));
        } else throw std::invalid_argument("probe_operation_unknown");
        disked::json::Limits limits;limits.bytes=2097152;limits.string_bytes=65536;std::cout<<disked::json::dump(result,limits)<<std::endl;
    } catch(const std::exception& e) {std::cout<<disked::json::dump(Value::object().put("error",Value::string(e.what())))<<std::endl;}
}
