#pragma once
#include "verification_operation.h"
#include "watch.h"
namespace disked {
constexpr const char* verification_event_feature="org.disked.verification-operation-events/1";
WatchProfile verification_watch_profile(const json::Value& exact_header);
}
