#pragma once
#include "protocol.h"
#include <memory>
#include <chrono>

namespace disked {
// Private frontend submission state. A queued call is not a protocol response
// and does not assert that a durable operation was admitted.
struct Submission {
    Outcome outcome;
    bool pending=false;
    Submission(Outcome value):outcome(std::move(value)) {}
    static Submission deferred() {Submission value(Outcome{});value.pending=true;return value;}
};
using FrontendHandler=std::function<Submission(const std::string&,const std::string&,const json::Value&,const std::string&)>;
using CompletionPoll=std::function<bool(Outcome&)>;

// One executing call and one result slot. Busy/unknown calls are never replaced
// by a new thread. The callback must own its inputs and must not reference a UI,
// session, registry, or any other object destroyed when the frontend closes.
class RequestChannel final {
    struct State;
    std::shared_ptr<State> state_;
public:
    RequestChannel();
    Submission submit(const std::string& request,std::function<Outcome()> callback);
    bool poll(Outcome& output);
    bool wait(Outcome& output,std::chrono::milliseconds duration);
};

// Sequential CLI/stdio adapter. After timeout the slot remains occupied until
// actual callback completion. A late observation is never another wire response.
class BoundedRequests final {
    RequestChannel channel_;
    bool late_=false;
public:
    Outcome run(const std::string& request,std::function<Outcome()> callback,
        Outcome expired,std::chrono::milliseconds duration,const std::function<bool()>& progress={});
};
}
