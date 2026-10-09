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
}
