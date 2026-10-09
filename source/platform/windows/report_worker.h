#pragma once
#include "report_operation.h"
namespace disked {
// Private native report-role admission, not a public command ABI. Ordinary
// acquisition metadata reads and owned report/state writes; no image I/O.
json::Value prepare_report_worker(const std::string& case_operation,const std::string& case_directory,
    const json::Value& policy,const std::string& destination,const std::string& execution_directory);
json::Value start_report_worker(const json::Value& definition,const json::Value& grant);
json::Value observe_report_worker(const std::string& operation,const std::string& execution_directory,bool cancel=false);
int run_report_worker(int argc,wchar_t** argv);
}
