#include "storage_fixture.h"
#include <algorithm>
#include <map>
namespace {
using V=disked::json::Value;
const V* fixture=nullptr;V trace=V::array();std::function<void()> entered;unsigned calls=0,errors=0;DWORD last_error=0;
std::map<std::pair<std::size_t,std::string>,std::size_t> positions;
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::uint64_t num(const V& v) {if(v.kind!=V::Kind::string || !disked::json::decimal_u64(v.text))throw std::invalid_argument("fixture_integer");return std::stoull(v.text);}
DWORD word(const V& v) {const auto n=num(v);if(n>0xffffffffULL)throw std::invalid_argument("fixture_integer");return static_cast<DWORD>(n);}
std::vector<unsigned char> unhex(const V& v) {
    const auto profile=fixture?fixture->find("profile"):nullptr;const auto limit=profile && profile->text=="identity-layout"?24576U:8192U;
    if(v.kind!=V::Kind::string || v.text.size()%2 || v.text.size()>limit)throw std::invalid_argument("fixture_hex");std::vector<unsigned char> b;
    auto nibble=[](char c)->unsigned {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);throw std::invalid_argument("fixture_hex");};
    for(std::size_t i=0;i<v.text.size();i+=2)b.push_back(static_cast<unsigned char>(nibble(v.text[i])*16+nibble(v.text[i+1])));return b;
}
BOOL WINAPI control(HANDLE handle,DWORD code,LPVOID input,DWORD input_bytes,LPVOID output,DWORD output_bytes,LPDWORD returned,LPOVERLAPPED overlapped) {
    const auto raw=reinterpret_cast<std::uintptr_t>(handle);if(raw<123 || raw-123>=get(*fixture,"subjects").items.size() || !output || !returned || overlapped)throw std::invalid_argument("fixture_arguments");
    const auto subject=static_cast<std::size_t>(raw-123);std::string component;
    if(code==IOCTL_STORAGE_QUERY_PROPERTY) {
        component="descriptor";if(!input || input_bytes!=12)throw std::invalid_argument("fixture_query_arguments");const auto q=static_cast<STORAGE_PROPERTY_QUERY*>(input);
        const auto profile=fixture->find("profile");const bool identity=profile && profile->text=="identity-layout";
        if(identity && q->PropertyId==StorageDeviceIdProperty)component="identifiers";
        else if(identity && q->PropertyId==StorageAccessAlignmentProperty)component="alignment";
        else if(q->PropertyId!=StorageDeviceProperty)throw std::invalid_argument("fixture_query_arguments");
        if(q->QueryType!=PropertyStandardQuery || q->AdditionalParameters[0])throw std::invalid_argument("fixture_query_arguments");
    } else {
        if(input || input_bytes)throw std::invalid_argument("fixture_query_arguments");
        component=code==IOCTL_STORAGE_GET_DEVICE_NUMBER?"number":code==IOCTL_DISK_GET_DRIVE_GEOMETRY_EX?"geometry":code==IOCTL_DISK_GET_LENGTH_INFO?"length":code==IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS?"extents":"";
        const auto profile=fixture->find("profile");if(code==IOCTL_DISK_GET_DRIVE_LAYOUT_EX && profile && profile->text=="identity-layout")component="layout";
        if(component.empty())throw std::invalid_argument("fixture_control_not_allowed");
    }
    ++calls;trace.items.push_back(V::object().put("component",V::string(component)).put("subject",V::string(std::to_string(subject))).put("control",V::string(std::to_string(code)))
        .put("input_bytes",V::string(std::to_string(input_bytes))).put("output_bytes",V::string(std::to_string(output_bytes))));
    if(calls==1){if(entered)entered();const auto p=fixture->find("worker_fault");const auto fault=p?p->text:"";
        if(fault=="delay")Sleep(350);if(fault=="hang")Sleep(INFINITE);if(fault=="crash")ExitProcess(23);}
    const auto& replies=get(get(get(*fixture,"subjects").items[subject],"replies"),component.c_str()).items;const auto position=positions[{subject,component}]++;
    if(position>=replies.size())throw std::invalid_argument("fixture_unexpected_repeat");const auto& r=replies[position];
    if(const auto p=r.find("throw"))if(p->boolean)throw std::runtime_error("injected_callback_exception");
    if(const auto p=r.find("throw_invalid_argument"))if(p->boolean)throw std::invalid_argument("injected_callback_exception");
    const auto bytes=unhex(get(r,"hex"));std::copy(bytes.begin(),bytes.begin()+std::min<std::size_t>(bytes.size(),output_bytes),static_cast<unsigned char*>(output));
    *returned=word(get(r,"returned"));last_error=word(get(r,"error"));return get(r,"ok").boolean?TRUE:FALSE;
}
DWORD WINAPI error() {++errors;return last_error;}

}
namespace disked { namespace nt_storage_fixture {
nt_inventory::StorageQueryApi api(const json::Value& value,const std::function<void()>& notify){
    fixture=&value;trace=V::array();calls=errors=0;last_error=0;positions.clear();entered=notify;
    nt_inventory::StorageQueryApi p;p.ioctl=&control;p.error=&error;
    if(const auto q=value.find("worker_fault")){if(q->text=="native_table")p=nt_inventory::native_storage_query_api();if(q->text=="native_error")p.error=&GetLastError;}return p;
}
unsigned call_count(){return calls;}unsigned error_count(){return errors;}json::Value calls_trace(){return trace;}
}}
