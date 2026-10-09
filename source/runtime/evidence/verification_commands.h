#pragma once
#include "protocol.h"
#include <functional>
namespace disked {
struct VerificationActions {
    std::function<json::Value(const json::Value&)> prepare;
    std::function<json::Value(const json::Value&,const json::Value&)> execute;
};
Outcome dispatch_verification(const Registry&,const std::string& request,const json::Value& parameters,const VerificationActions&);
Outcome verification_observation(const std::string& request,const json::Value& worker_reply);
Outcome verification_unresolved_request(const std::string& request,const json::Value& parameters);
}
