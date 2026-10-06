#include "gui_model.h"
#include "graph.h"
#include "command_registry.h"
#include "bootstrap_registry.h"
#include <algorithm>
#include <iostream>

using disked::json::Value;
int main() {
    const auto& registry=disked::command_registry();auto input=disked::fake_graph();
    disked::FrontendSession session(registry,input);Value discovery=Value::object(),commands=registry.commands;
    for(auto& c:commands.items) {
        bool available=false;for(const auto& row:bootstrap::commands)if(c.find("id")->text==row.id)available=row.implemented;
        c.put("availability",Value::string(available?"available":"unavailable"));
    }
    discovery.put("commands",commands);
    disked::GuiModel model(session,registry,discovery,[&](const std::string& id,const std::string& command,const Value& parameters,const std::string& revision) {
        if(disked::FrontendSession::handles(command))return session.dispatch(id,command,parameters,revision);
        return disked::completed(id,Value::object().put("test_static",Value::string(command)));
    });
    std::string line;
    while(std::getline(std::cin,line))try {
        const auto message=disked::json::parse(line);const auto* op=message.find("op");const auto kind=op?op->text:"";
        if(kind=="navigate")model.navigate(message.find("commands")->boolean);
        if(kind=="focus")model.focus(message.find("id")->text);
        if(kind=="open")model.open();if(kind=="clear")model.clear();if(kind=="refresh")model.refresh();
        if(kind=="stage")model.stage(message.find("command")->text,*message.find("parameters"));
        if(kind=="edit")model.edit(message.find("field")->text,message.find("value")->text);
        if(kind=="review")model.review();if(kind=="submit")model.submit();if(kind=="back")model.back();
        if(kind=="publish") {
            if(const auto* removed=message.find("remove")) {
                input.nodes.erase(std::remove_if(input.nodes.begin(),input.nodes.end(),[&](const disked::GraphNode& n){return n.id==removed->text;}),input.nodes.end());
                input.edges.erase(std::remove_if(input.edges.begin(),input.edges.end(),[&](const disked::GraphEdge& e){return e.from==removed->text || e.to==removed->text;}),input.edges.end());
            }
            session.publish(input);
        }
        Value result=Value::object().put("state",model.state()).put("rows",model.rows()).put("details",model.details()).put("graph",session.snapshot()->value());
        disked::json::Limits limits;limits.bytes=1048576;std::cout<<disked::json::dump(result,limits)<<std::endl;
    } catch(const std::exception& e) {std::cout<<disked::json::dump(Value::object().put("error",Value::string(e.what())))<<std::endl;}
}
