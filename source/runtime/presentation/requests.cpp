#include "requests.h"
#include <mutex>
#include <thread>
#include <condition_variable>

namespace disked {
struct RequestChannel::State {
    std::mutex mutex;
    std::condition_variable changed;
    bool busy=false,ready=false;
    Outcome result;
};
namespace {
Outcome unresolved(const std::string& request,const std::string& reason) {
    auto value=completed(request,json::Value{});value.exit_code=6;
    value.response.put("status",json::Value::string("unknown"));
    value.response.fields["diagnostics"].items.push_back(diagnostic(reason));return value;
}
}
RequestChannel::RequestChannel():state_(std::make_shared<State>()) {}
Submission RequestChannel::submit(const std::string& request,std::function<Outcome()> callback,std::size_t response_bytes) {
    if(!response_bytes || response_bytes>1048575)return refused(request,"request_resource_limit",3);
    const auto state=state_;
    std::lock_guard<std::mutex> lock(state->mutex);
    if(state->busy)return refused(request,"request_resource_limit",3);
    state->busy=true;
    try {
        // Reserve failure receipts before admitting the callback. Reporting an
        // allocation failure must not itself require another allocation in the
        // background thread or let an exception escape and terminate the UI.
        auto failure=unresolved(request,"request_completion_unresolved");
        auto invalid=unresolved(request,"request_completion_invalid");
        std::thread([state,request,callback,response_bytes,failure=std::move(failure),invalid=std::move(invalid)]() mutable {
            Outcome result=std::move(failure);
            try {
                auto candidate=callback();
                // The single result slot has the public frame bound and exact
                // correlation. A malformed/oversized reply cannot imply no effect.
                json::Limits limits;limits.bytes=response_bytes;json::dump(candidate.response,limits);
                const auto* id=candidate.response.find("request_id");
                if(!id || id->kind!=json::Value::Kind::string || id->text!=request || !validate_response(candidate.response).empty())
                    result=std::move(invalid);
                else result=std::move(candidate);
            } catch(...) {} // Preserve the preallocated unknown outcome.
            std::lock_guard<std::mutex> done(state->mutex);
            state->result=std::move(result);state->ready=true;state->changed.notify_one();
        }).detach();
    } catch(...) {state->busy=false;return refused(request,"request_thread_unavailable",3);}
    return Submission::deferred();
}
bool RequestChannel::poll(Outcome& output) {
    std::lock_guard<std::mutex> lock(state_->mutex);
    if(!state_->ready)return false;
    output=std::move(state_->result);state_->result=Outcome{};state_->ready=state_->busy=false;return true;
}
bool RequestChannel::wait(Outcome& output,std::chrono::milliseconds duration) {
    std::unique_lock<std::mutex> lock(state_->mutex);
    if(!state_->changed.wait_for(lock,duration,[&] {return state_->ready;}))return false;
    output=std::move(state_->result);state_->result=Outcome{};state_->ready=state_->busy=false;return true;
}
Outcome BoundedRequests::run(const std::string& request,std::function<Outcome()> callback,
    Outcome expired,std::chrono::milliseconds duration,const std::function<bool()>& progress,std::size_t response_bytes) {
    Outcome result;
    if(late_) {
        if(!channel_.poll(result))return refused(request,"request_resource_limit",3);
        // The previous exchange already received unknown. Durable operation
        // state is still in its explicit store; this late observation is neither
        // a second wire response nor proof of worker quiescence.
        late_=false;
    }
    auto submission=channel_.submit(request,std::move(callback),response_bytes);
    if(!submission.pending)return std::move(submission.outcome);
    if(!progress) {if(channel_.wait(result,duration))return result;}
    else {
        const auto end=std::chrono::steady_clock::now()+duration;
        do {
            if(!progress()) {late_=true;return refused(request,"output_error",4);}
            if(channel_.wait(result,std::chrono::milliseconds(10))) {
                if(!progress())return refused(request,"output_error",4);return result;
            }
        } while(std::chrono::steady_clock::now()<end);
    }
    late_=true;return expired;
}
}
