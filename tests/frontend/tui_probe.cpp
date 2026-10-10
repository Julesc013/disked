#include "tui_model.h"
#include "graph.h"
#include "health_observer.h"
#include "command_registry.h"
#include "bootstrap_registry.h"
#include <algorithm>
#include <iostream>

using disked::json::Value;
int main(int argc,char**) {
    const auto& registry=disked::command_registry();auto input=disked::fake_graph();
    disked::FrontendSession session(registry,input,{},disked::fake_health_observation);Value discovery=Value::object(),commands=registry.commands;
    for(auto& c:commands.items) {
        bool available=false;for(const auto& row:bootstrap::commands)if(c.find("id")->text==row.id)available=row.implemented;
        if(argc==2 && c.find("id")->text=="image.acquire")available=true;
        c.put("availability",Value::string(available?"available":"unavailable"));
    }
    discovery.put("commands",commands);
    disked::TuiModel model(session,registry,discovery,[&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
        if(disked::FrontendSession::handles(command))return session.dispatch(id,command,parameters,revision);
        auto result=Value::object().put("test_static",Value::string(command));if(command=="image.acquire")result.put("test_parameters",parameters);
        return disked::completed(id,result);
    });
    const std::map<std::string,disked::TextKey> keys={{"up",disked::TextKey::Up},{"down",disked::TextKey::Down},{"enter",disked::TextKey::Enter},
        {"pageup",disked::TextKey::PageUp},{"pagedown",disked::TextKey::PageDown},{"tab",disked::TextKey::Tab},{"backtab",disked::TextKey::BackTab},
        {"backspace",disked::TextKey::Backspace},{"escape",disked::TextKey::Escape},{"f2",disked::TextKey::F2},{"f3",disked::TextKey::F3},
        {"f4",disked::TextKey::F4},{"f5",disked::TextKey::F5},{"f6",disked::TextKey::F6},{"f9",disked::TextKey::F9},{"f10",disked::TextKey::F10}};
    std::string line;
    while(std::getline(std::cin,line))try {
        disked::json::Limits input_limits;input_limits.string_bytes=65536;
        auto message=disked::json::parse(line,input_limits);const auto* op=message.find("op");
        if(op && op->text=="key")model.input({keys.at(message.find("key")->text),"",message.find("repeat") && message.find("repeat")->boolean});
        if(op && op->text=="text")model.input({disked::TextKey::Text,message.find("text")->text,false});
        if(op && op->text=="stage")model.stage(message.find("command")->text,*message.find("parameters"));
        if(op && op->text=="publish") {
            if(const auto* removed=message.find("remove")) {
                input.nodes.erase(std::remove_if(input.nodes.begin(),input.nodes.end(),[&](const disked::GraphNode& n){return n.id==removed->text;}),input.nodes.end());
                input.edges.erase(std::remove_if(input.edges.begin(),input.edges.end(),[&](const disked::GraphEdge& e){return e.from==removed->text || e.to==removed->text;}),input.edges.end());
            }
            session.publish(input);
        }
        unsigned columns=80,rows=25;bool linear=false;
        if(const auto* v=message.find("columns"))columns=static_cast<unsigned>(std::stoul(v->text));
        if(const auto* v=message.find("rows"))rows=static_cast<unsigned>(std::stoul(v->text));
        if(const auto* v=message.find("linear"))linear=v->boolean;
        Value lines=Value::array();for(const auto& row:model.render(columns,rows,linear))lines.items.push_back(Value::string(row));
        Value result=Value::object().put("state",model.state()).put("lines",lines).put("graph",session.snapshot()->value());
        disked::json::Limits limits;limits.bytes=1048576;limits.string_bytes=6*65536+2;std::cout<<disked::json::dump(result,limits)<<std::endl;
    } catch(const std::exception& e) {std::cout<<disked::json::dump(Value::object().put("error",Value::string(e.what())))<<std::endl;}
}
