#pragma once
#include "file_acquisition.h"
#include "protocol.h"
#include "watch.h"
#include "commands.h"
namespace disked {
// Private admission model; not the stable public command or broker API.
json::Value prepare_acquisition_worker(const FileAcquisitionRequest&,const std::string& state_directory);
json::Value start_acquisition_worker(const json::Value& definition,const json::Value& grant);
json::Value observe_acquisition_worker(const std::string& operation_id,const std::string& state_directory,bool cancel=false);
Outcome dispatch_acquisition_operation(const std::string& request,const std::string& command,const json::Value& parameters);
Outcome watch_acquisition_worker(const std::string& request,const json::Value& parameters,const std::shared_ptr<WatchQueue>& events={});
int run_acquisition_worker(int argc,wchar_t** argv);
AcquisitionActions acquisition_actions();
}
