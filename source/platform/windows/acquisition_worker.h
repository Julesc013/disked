#pragma once
#include "file_acquisition.h"
namespace disked {
// Private admission model; not the stable public command or broker API.
json::Value prepare_acquisition_worker(const FileAcquisitionRequest&,const std::string& state_directory);
json::Value start_acquisition_worker(const json::Value& definition,const json::Value& grant);
json::Value observe_acquisition_worker(const std::string& operation_id,const std::string& state_directory,bool cancel=false);
int run_acquisition_worker(int argc,wchar_t** argv);
}
