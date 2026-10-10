#include "acquisition_worker.h"
#include <cstdio>
#include <cwchar>
using V=disked::json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::runtime_error("probe_input");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw std::runtime_error("probe_input");return p.text;}
int wmain(int argc,wchar_t** argv) {
    if(argc>1 && std::wcscmp(argv[1],L"__disked_acquisition_worker")==0)return disked::run_acquisition_worker(argc,argv);
    try {
        if(argc!=1)throw std::runtime_error("probe_input");std::string input;char block[4096];
        for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>65536)throw std::runtime_error("probe_input");if(n<sizeof(block))break;}
        const auto v=disked::json::parse(input);const auto mode=text(v,"mode");V result;
        if(mode=="prepare") {
            if(v.kind!=V::Kind::object || (v.fields.size()!=5 && v.fields.size()!=6))throw std::runtime_error("probe_input");
            disked::FileAcquisitionRequest r;r.source=text(v,"source");r.destination=text(v,"destination");r.map=text(v,"map");
            if(const auto resume=v.find("resume")) {if(resume->kind!=V::Kind::boolean)throw std::runtime_error("probe_input");r.resume=resume->boolean;}
            result=disked::prepare_acquisition_worker(r,text(v,"state_directory"));
        } else if(mode=="start") {
            if(v.kind!=V::Kind::object || v.fields.size()!=3)throw std::runtime_error("probe_input");
            result=disked::start_acquisition_worker(field(v,"definition"),field(v,"grant"));
        } else if(mode=="inspect" || mode=="cancel") {
            if(v.kind!=V::Kind::object || v.fields.size()!=3)throw std::runtime_error("probe_input");
            result=disked::observe_acquisition_worker(text(v,"operation_id"),text(v,"state_directory"),mode=="cancel");
        } else throw std::runtime_error("probe_input");
        std::puts(disked::json::dump(result).c_str());return 0;
    }catch(const std::exception& e) {std::puts(disked::json::dump(V::object().put("refusal",V::string(e.what()))).c_str());return 3;}
}
