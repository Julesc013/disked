#pragma once
#include "report_operation.h"
#include "export_commands.h"
#include "watch.h"
namespace disked {
// Private native report-role admission, not a public command ABI. Ordinary
// acquisition metadata reads and owned report/state writes; no image I/O.
json::Value prepare_report_worker(const std::string& case_operation,const std::string& case_directory,
    const json::Value& policy,const std::string& destination,const std::string& execution_directory);
json::Value start_report_worker(const json::Value& definition,const json::Value& grant);
json::Value observe_report_worker(const std::string& operation,const std::string& execution_directory,bool cancel=false);
Outcome watch_report_worker(const std::string& request,const json::Value& parameters,const std::shared_ptr<WatchQueue>& events={});
Outcome dispatch_report_operation(const std::string& request,const std::string& command,const json::Value& parameters);
ExportActions export_actions();
int run_report_worker(int argc,wchar_t** argv);
}
