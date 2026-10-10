#include "verification_worker.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_verification_worker")==0)return disked::run_verification_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char bytes[4096];
        for(;;) {const auto n=std::fread(bytes,1,sizeof(bytes),stdin);input.append(bytes,n);if(input.size()>4194304)throw std::runtime_error("probe_input");if(n<sizeof(bytes))break;}
        auto limits=disked::verification_operation::definition_limits();limits.bytes=4194304;limits.string_bytes=3145728;limits.values=262144;
        const auto value=disked::json::parse(input,limits);const auto mode=text(value,"mode");V result;
        if(mode=="prepare") {
            if(value.fields.size()!=6)throw std::runtime_error("probe_input");result=disked::prepare_verification_worker(text(value,"operation_id"),text(value,"case_directory"),text(value,"image"),text(value,"map"),text(value,"state_directory"));
        }else if(mode=="start") {
            if(value.fields.size()!=3)throw std::runtime_error("probe_input");result=disked::start_verification_worker(get(value,"definition"),get(value,"grant"));
        }else if(mode=="inspect" || mode=="cancel") {
            if(value.fields.size()!=3)throw std::runtime_error("probe_input");result=disked::observe_verification_worker(text(value,"operation_id"),text(value,"state_directory"),mode=="cancel");
        }else if(mode=="history") {
            if(value.fields.size()!=3)throw std::runtime_error("probe_input");const auto h=disked::verification_operation::read_history(text(value,"records"),get(value,"header"));
            result=V::object().put("state",h.state).put("complete",V::boolean_value(h.complete)).put("count",V::string(std::to_string(h.count))).put("last_digest",V::string(h.previous));
        }else if(mode=="watch") {
            if(value.fields.size()!=6)throw std::runtime_error("probe_input");result=disked::watch_verification_worker(text(value,"operation_id"),text(value,"state_directory"),text(value,"after_sequence"),text(value,"after_digest"),text(value,"worker_epoch"));
        }else throw std::runtime_error("probe_input");
        std::puts(disked::json::dump(result,limits).c_str());return 0;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
