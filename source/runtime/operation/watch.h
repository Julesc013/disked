#pragma once
#include "fake_operation.h"
#include <deque>
#include <cstdint>
#include <memory>
#include <mutex>

namespace disked {
constexpr const char* fake_event_feature="org.disked.fake-operation-events/1";
std::string validate_watch_parameters(const json::Value& parameters);
std::string validate_fake_event(const json::Value& event);

// Sequence belongs to an immutable operation/attempt/worker domain. Observer
// identity correlates one request; it never transfers execution ownership.
class WatchCursor final {
    std::string operation_,request_,observer_,worker_,digest_;
    std::uint64_t sequence_=0;
    bool snapshot_=false;
public:
    WatchCursor(const std::string& operation,const std::string& request,const std::string& observer,const json::Value& parameters);
    std::vector<json::Value> project(const fake_operation::History& history);
    std::string sequence() const {return std::to_string(sequence_);}
    const std::string& digest() const {return digest_;}
    const std::string& worker() const {return worker_;}
};
class WatchReader final {
    std::string operation_,worker_,digest_,observer_,request_;
    std::uint64_t sequence_=0;
    bool snapshot_allowed_=false;
public:
    WatchReader(const std::string& operation,const std::string& worker="",const std::string& sequence="0",
        const std::string& digest=std::string(64,'0'),bool snapshot_allowed=false);
    // Exact duplicate is false; invalid/gapped/conflicting events throw without
    // changing the last accepted cursor. Additive outer fields stay with caller.
    bool accept(const json::Value& event);
    std::string sequence() const {return std::to_string(sequence_);}
    const std::string& digest() const {return digest_;}
};
class WatchQueue final {
    std::mutex mutex_;
    std::deque<json::Value> events_;
    std::size_t total_count_=0,total_bytes_=0;
    bool closed_=false;
public:
    // Finite admission, never waits for a consumer; false means observer closed.
    bool push(const json::Value& event);
    bool pop(json::Value& event);
    void close();
};
}
