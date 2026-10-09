#include "requests.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <thread>
#include <new>
namespace {thread_local bool allocation_denied=false;}
void* operator new(std::size_t size) {
    if(allocation_denied)throw std::bad_alloc();
    if(auto* p=std::malloc(size?size:1))return p;throw std::bad_alloc();
}
void* operator new[](std::size_t size) {return ::operator new(size);}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete[](void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
void operator delete[](void* p,std::size_t) noexcept {std::free(p);}
using namespace disked;
using json::Value;
using Clock=std::chrono::steady_clock;
namespace {
void require(bool value,const char* message) {if(!value)throw std::runtime_error(message);}
struct Gate {
    std::mutex mutex;std::condition_variable changed;bool open=false;
    void wait() {std::unique_lock<std::mutex> lock(mutex);require(changed.wait_for(lock,std::chrono::seconds(5),[&]{return open;}),"gate_timeout");}
    void release() {std::lock_guard<std::mutex> lock(mutex);open=true;changed.notify_all();}
};
Outcome await(RequestChannel& channel) {
    Outcome result;const auto until=Clock::now()+std::chrono::seconds(3);
    while(!channel.poll(result)) {require(Clock::now()<until,"completion_timeout");std::this_thread::sleep_for(std::chrono::milliseconds(1));}
    return result;
}
}
int main()try {
    auto report=Value::object();RequestChannel channel;
    auto gate=std::make_shared<Gate>();auto calls=std::make_shared<std::atomic<unsigned>>(0);
    auto submitted=channel.submit("one",[gate,calls] {++*calls;gate->wait();return completed("one",Value::object().put("value",Value::string("exact outcome")));});
    require(submitted.pending && submitted.outcome.response.kind==Value::Kind::null,"pending_is_not_response");
    auto rejected=channel.submit("two",[calls] {++*calls;return completed("two",Value{});});
    require(!rejected.pending && rejected.outcome.exit_code==3,"busy_not_refused");
    require(rejected.outcome.response.find("diagnostics")->items.front().find("code")->text=="request_resource_limit","busy_diagnostic");
    Outcome result;const auto began=Clock::now();
    for(unsigned i=0;i<1000;++i)require(!channel.poll(result),"premature_completion");
    report.put("thousand_empty_polls_us",Value::number(std::to_string(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-began).count())));
    gate->release();result=await(channel);require(calls->load()==1,"second_callback_ran");
    require(result.response.find("request_id")->text=="one" && result.response.find("result")->find("value")->text=="exact outcome","completion_changed");
    require(!channel.poll(result),"completion_repeated");report.put("one_call_one_completion",Value::boolean_value(true));
    for(unsigned scenario=0;scenario<5;++scenario) {
        const auto id="invalid:"+std::to_string(scenario);
        require(channel.submit(id,[id,scenario] {
            if(scenario==0)return completed("another-request",Value{});
            if(scenario==1)throw std::runtime_error("effect_may_have_happened");
            if(scenario==2)return completed(id,Value::object().put("value",Value::string(std::string(32769,'x'))));
            // Keep allocations denied through exception handling and thread
            // teardown. An allocating error path would terminate this probe.
            if(scenario==4) {allocation_denied=true;throw std::bad_alloc();}
            auto invalid=completed(id,Value{});invalid.response.put("status",Value::string("invented"));return invalid;
        }).pending,"replacement_not_admitted_after_completion");
        result=await(channel);require(result.exit_code==6 && result.response.find("status")->text=="unknown","invalid_reply_not_unknown");
        require(result.response.find("request_id")->text==id,"invalid_reply_lost_correlation");
    }
    report.put("invalid_completions_unknown",Value::number("5"));
    report.put("allocation_failure_receipt_preallocated",Value::boolean_value(true));
    auto large=[](const std::string& id) {
        auto values=Value::array();for(unsigned i=0;i<4;++i)values.items.push_back(Value::string(std::string(20000,'x')));
        return completed(id,Value::object().put("values",values));
    };
    require(channel.submit("default-bound",[large] {return large("default-bound");}).pending,"default_bound_submission");
    require(await(channel).exit_code==6,"default_bound_was_widened");
    require(channel.submit("selected-bound",[large] {return large("selected-bound");},1048575).pending,"selected_bound_submission");
    require(await(channel).exit_code==0,"selected_bound_not_honoured");
    require(channel.submit("selected-value-bound",[] {
        auto values=Value::array();for(unsigned i=0;i<8193;++i)values.items.push_back(Value{});
        return completed("selected-value-bound",values);
    },1048575).pending,"selected_value_submission");
    require(await(channel).exit_code==6,"selected_bound_weakened_value_limit");
    unsigned denied_calls=0;
    for(const auto bytes:{std::size_t(0),std::size_t(1048576)}) {
        auto denied=channel.submit("invalid-bound",[&denied_calls] {++denied_calls;return completed("invalid-bound",Value{});},bytes);
        require(!denied.pending && denied.outcome.exit_code==3,"invalid_bound_admitted");
    }
    require(!denied_calls,"invalid_bound_dispatched_callback");
    report.put("explicit_finite_response_bound",Value::boolean_value(true));
    auto routing=[](const std::string& id) {
        auto out=completed(id,Value::object().put("state_directory",Value::string("owned-explicit-store")).put("definition_digest",Value::string("sha256:"+std::string(64,'a'))));
        out.response.put("status",Value::string("unknown"));out.exit_code=6;return out;
    };
    require(channel.submit("routed-throw",[]()->Outcome {throw std::runtime_error("owned_callback_failure");},65536,routing("routed-throw")).pending,"routed_throw_submission");
    result=await(channel);require(result.exit_code==6 && result.response.find("result")->find("state_directory")->text=="owned-explicit-store","throw_lost_routing");
    require(channel.submit("routed-budget",[large] {auto out=large("routed-budget");out.response.put("operation_id",Value::string("verify-op:"+std::string(32,'b')));return out;},65536,routing("routed-budget")).pending,"routed_budget_submission");
    result=await(channel);require(result.exit_code==6 && result.response.find("result")->find("definition_digest")->text=="sha256:"+std::string(64,'a') && result.response.find("operation_id")->text=="verify-op:"+std::string(32,'b'),"budget_lost_routing_or_id");
    require(channel.submit("invalid-routed",[] {return completed("other",Value{});},65536,routing("invalid-routed")).pending,"invalid_routing_submission");
    result=await(channel);require(result.exit_code==6 && result.response.find("result")->find("state_directory")->text=="owned-explicit-store","invalid_reply_lost_routing");
    auto wrong=routing("wrong-request");unsigned unsafe_calls=0;
    auto no=channel.submit("declared-request",[&unsafe_calls] {++unsafe_calls;return completed("declared-request",Value{});},65536,wrong);
    require(!no.pending && no.outcome.exit_code==3 && !unsafe_calls,"invalid_fallback_dispatched");
    report.put("unknown_preserves_routing_and_observed_id",Value::boolean_value(true));
    auto retained=std::make_shared<Gate>();auto finished=std::make_shared<std::atomic<bool>>(false);
    const auto before=Clock::now();
    {
        RequestChannel disconnected;
        require(disconnected.submit("disconnected",[retained,finished] {retained->wait();finished->store(true);return completed("disconnected",Value{});}).pending,"disconnect_submission");
    }
    const auto destruct=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-before).count();
    require(destruct<250,"destructor_waited_for_callback");retained->release();
    const auto deadline=Clock::now()+std::chrono::seconds(3);
    while(!finished->load()) {require(Clock::now()<deadline,"owned_callback_did_not_finish");std::this_thread::sleep_for(std::chrono::milliseconds(1));}
    report.put("disconnected_owner_ms",Value::number(std::to_string(destruct))).put("callback_owned_lifetime",Value::boolean_value(true));
    BoundedRequests bounded;auto stalled=std::make_shared<Gate>();auto dispatched=std::make_shared<std::atomic<unsigned>>(0);
    auto expired=[](const std::string& id) {auto out=completed(id,Value{});out.exit_code=6;out.response.put("status",Value::string("unknown"));return out;};
    const auto bounded_start=Clock::now();
    result=bounded.run("timed",[stalled,dispatched] {++*dispatched;stalled->wait();return completed("timed",Value{});},expired("timed"),std::chrono::milliseconds(20));
    require(result.exit_code==6,"wait_did_not_expire");
    require(Clock::now()-bounded_start<std::chrono::milliseconds(250),"wait_not_bounded");
    auto later=[dispatched] {++*dispatched;return completed("new",Value{});};
    result=bounded.run("busy",later,expired("busy"),std::chrono::milliseconds(20));
    require(result.exit_code==3 && response_exit(result.response)==3 && dispatched->load()==1,"timeout_replaced_callback");
    stalled->release();const auto after=Clock::now()+std::chrono::seconds(3);
    do {
        result=bounded.run("new",later,expired("new"),std::chrono::milliseconds(500));
        require(Clock::now()<after,"late_completion_not_retired");
        if(result.exit_code==3)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    } while(result.exit_code==3);
    require(result.exit_code==0 && result.response.find("request_id")->text=="new" && dispatched->load()==2,"late_reply_reused_or_call_retried");
    report.put("timed_slot_retained_until_completion",Value::boolean_value(true));
    std::cout<<json::dump(report)<<std::endl;return 0;
} catch(const std::exception& error) {std::cerr<<error.what()<<std::endl;return 1;}
