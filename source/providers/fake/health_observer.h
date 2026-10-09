#pragma once
#include "protocol.h"
namespace disked {
// Compiled fixture lookup only. No device, self-test, OS worker or file port.
Outcome fake_health_observation(const std::string& request,const json::Value& node,
    const std::string& revision,const json::Value& policy);
}
