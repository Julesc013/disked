#include "requests.h"
#include <mutex>
#include <thread>

namespace disked {
struct RequestChannel::State {
    std::mutex mutex;
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
Submission RequestChannel::submit(const std::string& request,std::function<Outcome()> callback) {
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
        std::thread([state,request,callback,failure=std::move(failure),invalid=std::move(invalid)]() mutable {
            Outcome result=std::move(failure);
            try {
                auto candidate=callback();
                // The single result slot has the public frame bound and exact
                // correlation. A malformed/oversized reply cannot imply no effect.
                json::dump(candidate.response);
                const auto* id=candidate.response.find("request_id");
                if(!id || id->kind!=json::Value::Kind::string || id->text!=request || !validate_response(candidate.response).empty())
                    result=std::move(invalid);
                else result=std::move(candidate);
            } catch(...) {} // Preserve the preallocated unknown outcome.
            std::lock_guard<std::mutex> done(state->mutex);
            state->result=std::move(result);state->ready=true;
        }).detach();
    } catch(...) {state->busy=false;return refused(request,"request_thread_unavailable",3);}
    return Submission::deferred();
}
bool RequestChannel::poll(Outcome& output) {
    std::lock_guard<std::mutex> lock(state_->mutex);
    if(!state_->ready)return false;
    output=std::move(state_->result);state_->result=Outcome{};state_->ready=state_->busy=false;return true;
}
}
