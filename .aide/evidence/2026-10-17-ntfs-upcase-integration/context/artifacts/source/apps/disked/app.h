#pragma once
#include "runtime/command/command.h"
#include "runtime/invocation/policy.h"
namespace disked {
int run_disked(const std::vector<std::string>& arguments,const InvocationHost& host);
}
