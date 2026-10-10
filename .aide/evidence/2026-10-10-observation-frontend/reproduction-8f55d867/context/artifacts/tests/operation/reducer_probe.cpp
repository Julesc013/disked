#include "fake_operation.h"
#include <iostream>
#include <memory>
using disked::json::Value;
namespace op=disked::fake_operation;
int main() {
    std::unique_ptr<op::Operation> operation;std::string history,previous(64,'0'),line;
    while(std::getline(std::cin,line))try {
        const auto input=disked::json::parse(line);const auto action=input.find("action")->text;Value result;
        if(action=="start") {operation.reset(new op::Operation(*input.find("binding")));history.clear();previous.assign(64,'0');}
        else if(action=="read") {const auto h=op::read_history(input.find("bytes")->text);result=h.state;}
        else if(action=="history")result=Value::string(history);
        else {
            if(!operation)throw std::invalid_argument("probe_not_started");
            const auto* from=input.find("origin");const auto* count=input.find("count");
            const bool changed=operation->advance(action,from?*from:op::origin(*operation->state().find("binding")),count?count->text:"");
            if(!changed) {std::cout<<disked::json::dump(operation->state())<<std::endl;continue;}
        }
        if(action!="read" && action!="history") {
            result=operation->state();const auto record=op::record(result,previous);history+=record;
            previous=disked::json::parse(record).find("digest")->text;
        }
        disked::json::Limits limits;limits.bytes=op::history_limit*2;
        std::cout<<disked::json::dump(result,limits)<<std::endl;
    } catch(const std::exception& error) {
        auto out=Value::object().put("error",Value::string(error.what()));
        if(operation)out.put("retained",operation->state());
        std::cout<<disked::json::dump(out)<<std::endl;
    }
}
