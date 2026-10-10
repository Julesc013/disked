#pragma once
#include "protocol.h"
#include <functional>
namespace disked {
// Inward service ports. No platform dependency, authenticated approval or
// implicit storage authority. Preparation reads; execution checks a separate
// exact-definition grant before invoking the effect port.
struct ExportActions {
    std::function<json::Value(const json::Value&)> prepare;
    std::function<json::Value(const json::Value&,const json::Value&)> execute;
};
Outcome dispatch_export(const Registry&,const std::string& request,const json::Value& parameters,const ExportActions&);
// Observation completion is a completed read, independent of logical effects.
Outcome export_observation(const std::string& request,const json::Value& worker_reply);
// Claims follow a validated explicit definition, never an operation prefix.
json::Value export_claims(json::Value value,const json::Value& definition);
Outcome export_unresolved_request(const std::string& request,const json::Value& parameters);
}
