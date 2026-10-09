#include "case_report.h"
#include "session.h"
#include <iostream>
#include <map>
#include <memory>
using V=disked::json::Value;
namespace h=disked::health::proposal;
namespace e=disked::evidence::proposal;
namespace {
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("probe_field");return *p;}
std::string text(const V& v,const char* key) {const auto& s=get(v,key);if(s.kind!=V::Kind::string)throw e::Error("probe_text");return s.text;}
V run(const V& input) {
    e::Case report(text(input,"case_id"),get(input,"code_identity"));
    std::map<std::string,std::unique_ptr<h::Capture>> captures;std::map<std::string,h::Ticket> tickets;
    V events=V::array();const auto& actions=get(input,"actions");if(actions.kind!=V::Kind::array || actions.items.size()>512)throw e::Error("probe_actions");
    for(const auto& action:actions.items) {
        V event=V::object();try {
            const auto op=text(action,"action");
            if(op=="capture") {std::unique_ptr<h::Capture> next(new h::Capture(get(action,"request")));captures[text(action,"as")]=std::move(next);}
            else if(op=="support")event.put("support",report.support(get(action,"policy")));
            else if(op=="append")report.append(text(action,"phase"),text(action,"origin"),text(action,"fixture_digest"),*captures.at(text(action,"capture")));
            else if(op=="display")event.put("display",V::string(disked::presentation_json(report.support(get(action,"policy")),e::case_limits())));
            else if(op=="mutate_returned_view") {auto copy=report.view();copy.put("case_id",V::string("forged"));copy.fields["records"].items.clear();}
            else {
                auto& capture=*captures.at(text(action,"capture"));
                if(op=="start")tickets[text(action,"as")]=capture.start(text(action,"source"));
                else if(op=="finish")event.put("accepted",V::boolean_value(capture.finish(tickets.at(text(action,"ticket")),get(action,"response"))));
                else if(op=="retire")event.put("changed",V::boolean_value(capture.retire(tickets.at(text(action,"ticket")))));
                else if(op=="timeout")event.put("changed",V::boolean_value(capture.timeout(tickets.at(text(action,"ticket")))));
                else if(op=="cancel")event.put("changed",V::boolean_value(capture.cancel()));
                else if(op=="next")capture.next_capture();else throw e::Error("probe_action");
            }
        } catch(const std::exception& error) {event.put("error",V::string(error.what()));}
        const auto current=report.view();
        if(!input.find("trace") || input.find("trace")->boolean)event.put("view",current);
        event.put("record_count",V::string(std::to_string(get(current,"records").items.size()))).put("case_digest",V::string(report.digest()));events.items.push_back(event);
    }
    return V::object().put("events",events).put("final",report.view()).put("case_digest",V::string(report.digest()))
        .put("physical_io",V::boolean_value(false)).put("file_export",V::boolean_value(false));
}
}
int main() {
    // Fixture driver bounds are deliberately larger than the case contract to
    // exercise rejected input and exact aggregate output limits independently.
    disked::json::Limits input;input.bytes=8388608;input.values=262144;input.string_bytes=100000;
    disked::json::Limits output;output.bytes=67108864;output.values=4194304;output.string_bytes=8388608;
    std::string line;while(std::getline(std::cin,line)) {
        V result;try {result=run(disked::json::parse(line,input));}catch(const std::exception& error) {result=V::object().put("error",V::string(error.what()));}
        std::cout<<disked::json::dump(result,output)<<'\n';
    }
}
