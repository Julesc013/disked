#include "platform/windows/report_worker.h"
#include <cstdio>
#include <cstring>
#include <cwchar>
#ifdef DISKED_REPORT_WORKER_TESTING
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
using V=disked::json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_report_worker")==0)return disked::run_report_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>4194304)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        auto limits=disked::report_operation::definition_limits();limits.bytes=4194304;limits.string_bytes=1048576;const auto v=disked::json::parse(input,limits);const auto mode=text(v,"mode");V result;
#ifdef DISKED_REPORT_WORKER_TESTING
        if(mode=="prepare-joined-trace" || mode=="prepare-joined-trace-mutate" || mode=="prepare-joined-trace-stream" ||
            mode=="prepare-trace-stream" || mode=="prepare-joined-trace-stream-wait") {
            const bool joined=mode!="prepare-trace-stream";
            const bool stream=mode=="prepare-joined-trace-stream" || mode=="prepare-trace-stream" || mode=="prepare-joined-trace-stream-wait";
            if(v.fields.size()!=(joined?8U:6U))throw std::runtime_error("probe_input");
            auto phases=V::array();
            auto selected_id=text(v,"operation_id"),selected_case=text(v,"case_directory"),selected_collection=joined?text(v,"collection_path"):"",
                selected_digest=joined?text(v,"collection_digest"):"",selected_destination=text(v,"destination"),selected_dir=text(v,"state_directory");
            auto selected_policy=field(v,"policy");bool mutated=false;
            auto sample=[&](const char* name) {
                if(phases.items.size()==10)throw std::runtime_error("probe_phase_budget");
                const auto prior_error=GetLastError();
                if(!mutated && mode=="prepare-joined-trace-mutate") {
                    selected_id=selected_case=selected_collection=selected_digest=selected_destination=selected_dir="changed-by-caller";
                    selected_policy=V::object();mutated=true;
                }
                FILETIME created{},exited{},kernel{},user{};IO_COUNTERS io{};
                const auto stamp=GetTickCount64();
                const bool cpu=GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user)!=FALSE;
                const bool observed_io=GetProcessIoCounters(GetCurrentProcess(),&io)!=FALSE;
                const auto ticks=[](const FILETIME& t) {return (static_cast<std::uint64_t>(t.dwHighDateTime)<<32)|t.dwLowDateTime;};
                phases.items.push_back(V::object().put("phase",V::string(name)).put("ticks_ms",V::string(std::to_string(stamp)))
                    .put("cpu_observed",V::boolean_value(cpu)).put("kernel_100ns",V::string(std::to_string(ticks(kernel))))
                    .put("user_100ns",V::string(std::to_string(ticks(user)))).put("io_observed",V::boolean_value(observed_io))
                    .put("read_operations",V::string(std::to_string(io.ReadOperationCount)))
                    .put("read_bytes",V::string(std::to_string(io.ReadTransferCount)))
                    .put("other_operations",V::string(std::to_string(io.OtherOperationCount))));
                if(stream) {
                    const auto& observation=phases.items.back();
                    std::puts(disked::json::dump(observation).c_str());std::fflush(stdout);
                    if(mode=="prepare-joined-trace-stream-wait" && std::strcmp(name,"image_begin")==0)Sleep(6000);
                }
                SetLastError(prior_error);
            };
            if(joined)result=disked::prepare_joined_report_worker_testing(selected_id,selected_case,selected_collection,selected_digest,
                selected_policy,selected_destination,selected_dir,sample);
            else result=disked::prepare_report_worker_testing(selected_id,selected_case,selected_policy,selected_destination,selected_dir,sample);
            result.put("phase_trace",std::move(phases));
            if(mode=="prepare-joined-trace-mutate")result.put("caller_mutation_attempted",V::boolean_value(mutated));
        }else
#endif
        if(mode=="prepare-joined") {
            if(v.fields.size()!=8)throw std::runtime_error("probe_input");result=disked::prepare_joined_report_worker(text(v,"operation_id"),text(v,"case_directory"),
                text(v,"collection_path"),text(v,"collection_digest"),field(v,"policy"),text(v,"destination"),text(v,"state_directory"));
        }else if(mode=="prepare") {
            if(v.fields.size()!=6)throw std::runtime_error("probe_input");result=disked::prepare_report_worker(text(v,"operation_id"),text(v,"case_directory"),field(v,"policy"),text(v,"destination"),text(v,"state_directory"));
        }else if(mode=="start") {
            if(v.fields.size()!=3)throw std::runtime_error("probe_input");result=disked::start_report_worker(field(v,"definition"),field(v,"grant"));
        }else if(mode=="inspect" || mode=="cancel") {
            if(v.fields.size()!=3)throw std::runtime_error("probe_input");result=disked::observe_report_worker(text(v,"operation_id"),text(v,"state_directory"),mode=="cancel");
        }else if(mode=="history") {
            if(v.fields.size()!=3)throw std::runtime_error("probe_input");const auto h=disked::report_operation::read_history(text(v,"records"),field(v,"header"));
            result=V::object().put("state",h.state).put("complete",V::boolean_value(h.complete)).put("count",V::string(std::to_string(h.count))).put("last_digest",V::string(h.previous));
        }else throw std::runtime_error("probe_input");
        std::puts(disked::json::dump(result,limits).c_str());return 0;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
