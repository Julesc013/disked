#pragma once
#include "command.h"
#include "policy.h"
namespace disked {
int run_cli(const std::vector<std::string>& arguments,const InvocationHost& host);
}
