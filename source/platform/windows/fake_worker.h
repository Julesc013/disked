#pragma once
#include "protocol.h"
namespace disked {
bool fake_worker_command(const std::string& command);
Outcome dispatch_fake_worker(const std::string& request,const std::string& command,const json::Value& parameters);
// Private self-spawn entry. It accepts inherited capabilities, never a target path.
int run_fake_worker(int argc,wchar_t** argv);
}
