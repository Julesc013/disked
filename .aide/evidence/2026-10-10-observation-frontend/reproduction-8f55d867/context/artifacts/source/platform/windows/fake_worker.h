#pragma once
#include "protocol.h"
#include "watch.h"
namespace disked {
bool fake_worker_command(const std::string& command);
Outcome dispatch_fake_worker(const std::string& request,const std::string& command,const json::Value& parameters);
Outcome watch_fake_worker(const std::string& request,const json::Value& parameters,const std::shared_ptr<WatchQueue>& events={});
// Private self-spawn entry. It accepts inherited capabilities, never a target path.
int run_fake_worker(int argc,wchar_t** argv);
}
