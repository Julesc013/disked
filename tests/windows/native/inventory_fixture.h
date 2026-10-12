#pragma once
#include "providers/windows/inventory_session.h"
#include "runtime/graph/snapshot.h"
#include "storage_fixture.h"
#include "volume_fixture.h"
#include <algorithm>
#include <cstdio>

namespace disked_inventory_fixture {
using V=disked::json::Value;namespace n=disked::nt_inventory;
inline const V& field(const V& v,const char* name){const auto* p=v.find(name);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
inline std::string text(const V& v,const char* name){const auto& p=field(v,name);if(p.kind!=V::Kind::string)throw std::invalid_argument("fixture_shape");return p.text;}
inline void require(bool value,const char* why){if(!value)throw std::runtime_error(why);}
inline disked::json::Limits receipt_limits(){auto l=disked::json::Limits{};l.bytes=33554432;l.values=1048576;l.depth=40;l.string_bytes=8388608;return l;}
inline void print(const V& v){std::puts(disked::json::dump(v,receipt_limits()).c_str());std::fflush(stdout);}
inline void fixture_path(const wchar_t* raw){
    const std::wstring path(raw);if(path.size()<8 || !((path[0]>=L'A' && path[0]<=L'Z') || (path[0]>=L'a' && path[0]<=L'z')) || path[1]!=L':' || path[2]!=L'\\' || path.find(L':',2)!=std::wstring::npos || path.substr(path.size()-5)!=L".json")throw std::invalid_argument("fixture_path");
    for(std::size_t at=3;at<path.size();){
        const auto end=path.find_first_of(L"\\/",at);const auto component=path.substr(at,end==std::wstring::npos?end:end-at);
        if(component.empty() || component.back()==L' ' || component.back()==L'.' || component.find_first_of(L"<>\"|?*")!=std::wstring::npos ||
            std::any_of(component.begin(),component.end(),[](wchar_t c){return c<32;}))throw std::invalid_argument("fixture_path");
        auto stem=component.substr(0,component.find(L'.'));while(!stem.empty() && stem.back()==L' ')stem.pop_back();
        for(auto& c:stem)if(c>=L'a' && c<=L'z')c=static_cast<wchar_t>(c-L'a'+L'A');
        const bool numbered=stem.size()==4 && (stem.substr(0,3)==L"COM" || stem.substr(0,3)==L"LPT") &&
            ((stem[3]>=L'1' && stem[3]<=L'9') || stem[3]==L'\u00b9' || stem[3]==L'\u00b2' || stem[3]==L'\u00b3');
        if(stem==L"CON" || stem==L"NUL" || stem==L"AUX" || stem==L"PRN" || numbered)throw std::invalid_argument("fixture_path");
        if(end==std::wstring::npos)break;at=end+1;
    }
}
inline V read(const wchar_t* path){
    FILE* file=nullptr;if(_wfopen_s(&file,path,L"rb") || !file)throw std::invalid_argument("fixture_input_unavailable");
    std::string data;char block[8192];
    try{for(;;){const auto size=std::fread(block,1,sizeof(block),file);if(data.size()+size>1048576)throw std::invalid_argument("fixture_input_limit");
        data.append(block,size);if(size<sizeof(block)){if(std::ferror(file))throw std::invalid_argument("fixture_input_error");break;}}}
    catch(...){std::fclose(file);throw;}std::fclose(file);
    auto l=disked::json::Limits{};l.bytes=1048576;l.values=131072;l.depth=35;return disked::json::parse(data,l);
}
struct ReceiptFile final {
    HANDLE handle=INVALID_HANDLE_VALUE;
    explicit ReceiptFile(const wchar_t* path){handle=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);if(handle==INVALID_HANDLE_VALUE)throw std::invalid_argument("fixture_receipt_unavailable");}
    ~ReceiptFile(){if(handle!=INVALID_HANDLE_VALUE)CloseHandle(handle);}
    ReceiptFile(const ReceiptFile&)=delete;ReceiptFile& operator=(const ReceiptFile&)=delete;
    void write(const V& value){const auto data=disked::json::dump(value,receipt_limits());std::size_t at=0;
        while(at<data.size()){const auto size=static_cast<DWORD>((std::min)(data.size()-at,std::size_t(131072)));DWORD written=0;
            if(!WriteFile(handle,data.data()+at,size,&written,nullptr) || written!=size)throw std::runtime_error("fixture_receipt_write");at+=written;}
        if(!FlushFileBuffers(handle))throw std::runtime_error("fixture_receipt_flush");
    }
};
inline V publication_value(const std::shared_ptr<const n::InventoryPublication>& publication,
    const std::shared_ptr<const disked::GraphSnapshot>& snapshot){
    auto artifacts=V::object(),bindings=V::array(),resolved=V::array(),sources=V::array();
    for(const auto& source:publication->view()->sources)sources.items.push_back(V::object().put("id",V::string(source.id))
        .put("state",V::string(disked::source_state_name(source.state))).put("outstanding",V::boolean_value(source.outstanding)));
    for(const auto& node:publication->view()->graph.nodes){
        const auto& frame=publication->frame(node.id);const auto digest=disked::digest_sha256(disked::json::dump(frame,
            node.observation.source=="storage"?n::storage_observation_limits():n::volume_inventory_limits()));
        const auto name="frame:"+digest;if(!artifacts.find(name))artifacts.put(name,frame);
        bindings.items.push_back(V::object().put("node",V::string(node.id)).put("artifact",V::string(name)).put("context",field(node.observation.payload,"worker_context")));
        if(node.kind=="storage-identity-observation")for(const auto& ref:field(node.observation.payload,"references").fields){
            const auto key=text(ref.second,"kind")+":"+text(ref.second,"digest");if(!artifacts.find(key))artifacts.put(key,publication->resolve(node.id,ref.first));
            resolved.items.push_back(V::object().put("node",V::string(node.id)).put("name",V::string(ref.first)).put("reference",ref.second).put("artifact",V::string(key)));}
    }
    return V::object().put("graph",snapshot->value()).put("sources",sources).put("bindings",bindings).put("artifacts",artifacts).put("resolved",resolved);
}
}
