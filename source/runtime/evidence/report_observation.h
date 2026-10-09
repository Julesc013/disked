#pragma once
#include "report_operation.h"
#include "watch.h"
namespace disked {
constexpr const char* report_event_feature="org.disked.report-operation-events/1";
// Prototype retained request/record profile, never execution authority.
WatchProfile report_watch_profile(const json::Value& exact_header);
}
