#pragma once
#include "operation.h"
#include "watch.h"
namespace disked {
constexpr const char* acquisition_event_feature="org.disked.acquisition-operation-events/1";
WatchProfile acquisition_watch_profile(const json::Value& exact_definition);
}
