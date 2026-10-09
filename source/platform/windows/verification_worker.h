#pragma once
#include "verification_operation.h"
namespace disked {
json::Value prepare_verification_worker(const std::string& case_operation,const std::string& case_directory,
    const std::string& image,const std::string& map,const std::string& execution_directory);
json::Value start_verification_worker(const json::Value& definition,const json::Value& grant);
json::Value observe_verification_worker(const std::string& operation,const std::string& directory,bool cancel=false);
json::Value watch_verification_worker(const std::string& operation,const std::string& directory,
    const std::string& after_sequence,const std::string& after_digest,const std::string& worker_epoch);
int run_verification_worker(int argc,wchar_t** argv);
}
