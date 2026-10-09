#include "report_worker.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_report_worker")==0)return disked::run_report_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>4194304)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        auto limits=disked::report_operation::definition_limits();limits.bytes=4194304;limits.string_bytes=1048576;const auto v=disked::json::parse(input,limits);const auto mode=text(v,"mode");V result;
        if(mode=="prepare") {
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
