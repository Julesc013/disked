#include "capture.h"
#include "session.h"
#include <iostream>
#include <memory>
#include <new>
#include <cstdlib>

// Fail the nth allocation on demand, only in this native test executable.
// Probe input and response rendering run with ordinary allocation enabled.
namespace {thread_local long long allocations_until_failure=-1;}
void* operator new(std::size_t size) {
    if(allocations_until_failure==0) {allocations_until_failure=-1;throw std::bad_alloc();}
    if(allocations_until_failure>0)--allocations_until_failure;
    if(auto* p=std::malloc(size?size:1))return p;throw std::bad_alloc();
}
void* operator new[](std::size_t size) {return ::operator new(size);}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete[](void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
void operator delete[](void* p,std::size_t) noexcept {std::free(p);}
using namespace disked;using json::Value;
std::string text(const Value& value,const char* field) {
    const auto* item=value.find(field);if(!item || item->kind!=Value::Kind::string)throw std::invalid_argument("probe_field");return item->text;
}
std::uint64_t number(const Value& value,const char* field) {
    const auto raw=text(value,field);if(!json::decimal_u64(raw))throw std::invalid_argument("probe_number");return std::stoull(raw);
}
Value wide(std::uint64_t value) {return Value::string(std::to_string(value));}
Value key_value(const CaptureKey& key) {return Value::object().put("source",Value::string(key.source)).put("capture",wide(key.capture)).put("worker",wide(key.worker));}
CaptureKey key(const Value& value) {return {text(value,"source"),number(value,"capture"),number(value,"worker")};}
Value source(const CaptureSource& item) {
    return Value::object().put("id",Value::string(item.id)).put("state",Value::string(source_state_name(item.state)))
        .put("outstanding",Value::boolean_value(item.outstanding)).put("attempt",key_value(item.attempt))
        .put("reason",Value::string(item.reason)).put("platform",Value::string(item.platform));
}
Value view(const std::shared_ptr<const CaptureView>& current) {
    auto sources=Value::array();for(const auto& item:current->sources)sources.items.push_back(source(item));
    return Value::object().put("capture",wide(current->capture)).put("sequence",wide(current->sequence))
        .put("graph",GraphSnapshot::create(current->graph,current->capture)->value()).put("sources",sources);
}
GraphInput graph(const Value& value) {
    GraphInput result;
    for(const auto& item:value.find("nodes")->items) {
        GraphNode node{text(item,"id"),"block-device",text(item,"identity"),text(item,"generation"),text(item,"label"),text(item,"state"),text(item,"capacity"),{}};
        if(const auto* aliases=item.find("aliases"))for(const auto& alias:aliases->items)node.aliases.push_back(alias.text);
        result.nodes.push_back(std::move(node));
    }
    if(const auto* edges=value.find("edges"))for(const auto& item:edges->items)result.edges.push_back({text(item,"from"),text(item,"to"),text(item,"kind")});
    if(const auto* omissions=value.find("omissions"))for(const auto& item:omissions->items)result.omissions.push_back(item.text);
    return result;
}
int main() {
    std::unique_ptr<ObservationCapture> capture;std::vector<std::shared_ptr<const CaptureView>> retained;
    std::string line;
    while(std::getline(std::cin,line)) {
        try {
            const auto input=json::parse(line);const auto op=text(input,"op");Value result;
            if(op=="session_atomic") {
                Registry registry;const auto initial=graph(*input.find("initial"));
                std::shared_ptr<const GraphInput> incoming;std::size_t polls=0;
                FrontendSession session(registry,initial,[&]() {++polls;return incoming;});
                const auto before=session.snapshot();incoming=std::make_shared<const GraphInput>(graph(*input.find("updated")));
                bool failed=false,changed=false;
                allocations_until_failure=static_cast<long long>(number(input,"allocation_failure"));
                try {changed=session.refresh_observations();allocations_until_failure=-1;}
                catch(const std::bad_alloc&) {allocations_until_failure=-1;failed=true;}
                catch(...) {allocations_until_failure=-1;throw;}
                const bool retried=session.refresh_observations();const auto current=session.snapshot();
                const auto prior_polls=polls;
                const auto outcome=session.act({ActionKind::Inspect,initial.nodes.front().id,current->revision(),"probe"});
                result=Value::object().put("failed",Value::boolean_value(failed)).put("changed",Value::boolean_value(changed))
                    .put("retried",Value::boolean_value(retried)).put("old",before->value()).put("current",current->value())
                    .put("action_polls",wide(polls-prior_polls)).put("action_exit",wide(outcome.exit_code));
            } else if(op=="init") {
                std::vector<std::string> sources;for(const auto& item:input.find("sources")->items)sources.push_back(item.text);
                capture.reset(new ObservationCapture(sources));retained.clear();result=view(capture->snapshot());
            } else {
                if(!capture)throw std::invalid_argument("probe_uninitialized");
                if(op=="view")result=view(capture->snapshot());
                else if(op=="retain") {retained.push_back(capture->snapshot());result=wide(retained.size()-1);}
                else if(op=="retained")result=view(retained.at(static_cast<std::size_t>(number(input,"index"))));
                else if(op=="start")result=key_value(capture->start(text(input,"source")));
                else if(op=="timeout")result=Value::boolean_value(capture->timeout(key(*input.find("key"))));
                else if(op=="next") {capture->next_capture();result=view(capture->snapshot());}
                else if(op=="finish") {
                    const auto binding=key(*input.find("key"));const auto content=graph(*input.find("graph"));
                    if(input.find("allocation_failure"))allocations_until_failure=static_cast<long long>(number(input,"allocation_failure"));
                    bool changed=false;
                    try {changed=capture->finish(binding,content);allocations_until_failure=-1;}
                    catch(...) {allocations_until_failure=-1;throw;}
                    result=Value::boolean_value(changed);
                } else if(op=="fail") {
                    const auto state=text(input,"state");const auto selected=state=="denied"?SourceState::Denied:
                        state=="malformed"?SourceState::Malformed:state=="unavailable"?SourceState::Unavailable:SourceState::Pending;
                    result=Value::boolean_value(capture->fail(key(*input.find("key")),selected,text(input,"reason"),text(input,"platform")));
                } else if(op=="changes") {
                    const auto update=capture->changes(number(input,"capture"),number(input,"after"));auto notices=Value::array();
                    for(const auto& item:update.notices)notices.items.push_back(Value::object().put("sequence",wide(item.sequence))
                        .put("capture",wide(item.capture)).put("source",source(item.source)));
                    result=Value::object().put("resnapshot",Value::boolean_value(update.resnapshot)).put("notices",notices).put("current",view(update.current));
                } else throw std::invalid_argument("probe_operation");
            }
            json::Limits limits;limits.bytes=1048576;std::cout<<json::dump(result,limits)<<std::endl;
        } catch(const std::bad_alloc&) {std::cout<<"{\"error\":\"allocation_failed\"}"<<std::endl;}
        catch(const std::exception& error) {std::cout<<json::dump(Value::object().put("error",Value::string(error.what())))<<std::endl;}
    }
}
