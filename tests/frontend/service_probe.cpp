#include "session.h"
#include "graph.h"
#include "health_observer.h"
#include "command_registry.h"
#include <iostream>

using disked::json::Value;
std::string text(const Value& value,const std::string& key) {return value.find(key)->text;}
std::vector<std::string> strings(const Value& value) {
    std::vector<std::string> out;for(const auto& v:value.items)out.push_back(v.text);return out;
}
disked::GraphInput graph(const Value& value) {
    disked::GraphInput out;
    for(const auto& n:value.find("nodes")->items) {
        const auto& p=*n.find("properties");
        out.nodes.push_back({text(n,"id"),text(n,"kind"),text(p,"identity"),text(p,"media_generation"),text(p,"label"),text(p,"state"),text(p,"capacity_bytes"),strings(*p.find("aliases"))});
    }
    for(const auto& e:value.find("edges")->items)out.edges.push_back({text(e,"from"),text(e,"to"),text(e,"kind")});
    out.omissions=strings(*value.find("omissions"));return out;
}
int main(int argc,char**) {
    disked::FrontendSession session(disked::command_registry(),disked::fake_graph(),{},argc==2?disked::FrontendSession::HealthObservation{}:disked::fake_health_observation);
    std::vector<std::shared_ptr<const disked::GraphSnapshot>> retained;
    std::string line;
    while(std::getline(std::cin,line)) {
        try {
            const auto input=disked::json::parse(line);const auto op=text(input,"op");Value result;
            if(op=="query") {retained.push_back(session.snapshot());result=session.snapshot()->value();}
            else if(op=="retained")result=retained.at(static_cast<std::size_t>(std::stoul(text(input,"index"))))->value();
            else if(op=="selection")result=session.selection();
            else if(op=="publish") {session.publish(graph(*input.find("graph")));result=session.snapshot()->value();}
            else if(op=="act") {
                const auto kind=text(input,"kind");
                const auto action=kind=="inspect"?disked::ActionKind::Inspect:kind=="select"?disked::ActionKind::Select:disked::ActionKind::ClearSelection;
                result=session.act({action,text(input,"target"),text(input,"revision"),"probe"}).response;
            } else if(op=="dispatch")result=session.dispatch("probe",text(input,"command"),*input.find("parameters"),text(input,"revision")).response;
            else if(op=="hash")result=Value::string(disked::digest_sha256(text(input,"bytes")));
            else if(op=="display")result=Value::string(disked::presentation_json(*input.find("value")));
            else throw std::invalid_argument("unknown_probe_operation");
            std::cout<<disked::json::dump(result)<<std::endl;
        } catch(const std::exception& error) {
            std::cout<<disked::json::dump(Value::object().put("error",Value::string(error.what())))<<std::endl;
        }
    }
}
