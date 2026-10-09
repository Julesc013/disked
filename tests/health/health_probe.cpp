#include "health.h"
#include <iostream>
#include <map>

namespace h=disked::health::proposal;
using V=disked::json::Value;
namespace {
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw h::Error("probe_field");return *p;}
std::string str(const V& v,const char* key) {const auto& x=get(v,key);if(x.kind!=V::Kind::string)throw h::Error("probe_string");return x.text;}
std::uint64_t number(const V& v,const char* key) {const auto s=str(v,key);if(!disked::json::decimal_u64(s))throw h::Error("probe_integer");return std::stoull(s);}
V run(const V& input) {
    h::Capture capture(get(input,"request"),input.find("capture_seed")?number(input,"capture_seed"):1,input.find("worker_seed")?number(input,"worker_seed"):0);
    std::map<std::string,h::Ticket> keys;V events=V::array();std::uint64_t queries=0;
    const auto& actions=get(input,"actions");if(actions.kind!=V::Kind::array || actions.items.size()>512)throw h::Error("probe_actions");
    for(const auto& action:actions.items) {
        V event=V::object();
        try {
            const auto name=str(action,"action");
            if(name=="start") {const auto ticket=capture.start(str(action,"source"));keys[str(action,"as")]=ticket;++queries;event.put("ticket",h::ticket_value(ticket));}
            else if(name=="cancel")event.put("changed",V::boolean_value(capture.cancel()));
            else if(name=="next")capture.next_capture();
            else if(name=="support")event.put("support",capture.support(get(action,"policy")));
            else {
                const auto key=action.find("ticket")?h::read_ticket(get(action,"ticket")):keys.at(str(action,"key"));
                if(name=="finish")event.put("accepted",V::boolean_value(capture.finish(key,get(action,"response"))));
                else if(name=="timeout")event.put("changed",V::boolean_value(capture.timeout(key)));
                else if(name=="retire")event.put("changed",V::boolean_value(capture.retire(key)));
                else throw h::Error("probe_action");
            }
        }catch(const std::exception& error) {event.put("error",V::string(error.what()));}
        event.put("view",capture.view());events.items.push_back(std::move(event));
    }
    return V::object().put("events",events).put("final",capture.view()).put("queries",V::string(std::to_string(queries)))
        .put("physical_io",V::boolean_value(false)).put("self_tests",V::boolean_value(false));
}
}
int main() {
    // Test driver is private; its outer bounds allow multi-action boundary cases.
    disked::json::Limits input;input.bytes=2097152;input.string_bytes=100000;input.values=131072;
    disked::json::Limits output;output.bytes=16777216;output.values=262144;output.string_bytes=8192;
    std::string line;
    while(std::getline(std::cin,line)) {
        V result;try {result=run(disked::json::parse(line,input));}catch(const std::exception& error) {result=V::object().put("error",V::string(error.what()));}
        std::cout<<disked::json::dump(result,output)<<'\n';
    }
}
