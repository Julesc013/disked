#pragma once
#include "protocol.h"
#include <cstdint>
#include <functional>
namespace disked {
struct AcquisitionCommandError : std::runtime_error {
    std::uint32_t platform_code;
    explicit AcquisitionCommandError(const char* code,std::uint32_t platform=0):std::runtime_error(code),platform_code(platform) {}
};
// Inward-facing ports. Preparation reads metadata only; execution has a
// separately checked exact-definition grant. No platform/provider dependency.
struct AcquisitionActions {
    std::function<json::Value(const json::Value&)> prepare;
    std::function<json::Value(const json::Value&,const json::Value&)> execute;
};
Outcome dispatch_acquisition(const Registry&,const std::string& request,
    const json::Value& parameters,const AcquisitionActions&);
// An observation is a completed read, independent of the logical operation's
// outcome. Execution completion requires the acquisition postcondition.
Outcome acquisition_observation(const std::string& request,const json::Value& worker_reply);
}
