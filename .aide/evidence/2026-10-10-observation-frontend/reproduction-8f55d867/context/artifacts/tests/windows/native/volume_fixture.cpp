#include "volume_fixture.h"
#include <algorithm>
#include <cstdio>
#include <iterator>
#include <stdexcept>
#include <io.h>
#include <fcntl.h>
namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
const V* fixture=nullptr;std::size_t current=0;unsigned calls=0,mount_calls=0,closes=0;DWORD last_error=0;
V trace=V::array();std::function<void()> entered;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::invalid_argument("fixture_shape");return *p;}
std::wstring units(const V& v) {
    if(v.kind!=V::Kind::array || v.items.size()>4096)throw std::invalid_argument("fixture_units");std::wstring out;
    for(const auto& x:v.items) {if(x.kind!=V::Kind::string || !disked::json::decimal_u64(x.text) || std::stoull(x.text)>65535)throw std::invalid_argument("fixture_units");out+=static_cast<wchar_t>(std::stoul(x.text));}return out;
}
DWORD number(const V& v) {if(v.kind!=V::Kind::string || !disked::json::decimal_u64(v.text) || std::stoull(v.text)>0xffffffffULL)throw std::invalid_argument("fixture_integer");return static_cast<DWORD>(std::stoul(v.text));}
bool flag(const V& v) {if(v.kind!=V::Kind::boolean)throw std::invalid_argument("fixture_boolean");return v.boolean;}
void log(const char* function,DWORD count=0) {++calls;trace.items.push_back(V::object().put("api",V::string(function)).put("buffer_units",V::string(std::to_string(count))));}
bool name(LPWSTR buffer,DWORD size) {
    const auto& names=get(*fixture,"names").items;
    if(current>=names.size()) {last_error=number(get(*fixture,"terminal_error"));return false;}
    const auto value=units(names[current]);const auto count=std::min<std::size_t>(size,value.size());std::copy(value.begin(),value.begin()+count,buffer);return true;
}
HANDLE WINAPI first(LPWSTR buffer,DWORD size) {
    log("FindFirstVolumeW",size);current=0;if(entered)entered();
    const auto value=fixture->find("worker_fault");const auto fault=value&&value->kind==V::Kind::string?value->text:"";
    if(fault=="delay")Sleep(350);if(fault=="hang")Sleep(INFINITE);if(fault=="crash")ExitProcess(23);
    return name(buffer,size)?reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(123)):INVALID_HANDLE_VALUE;
}
BOOL WINAPI next(HANDLE handle,LPWSTR buffer,DWORD size) {log("FindNextVolumeW",size);if(handle!=reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(123)))throw std::invalid_argument("fixture_handle");++current;mount_calls=0;return name(buffer,size)?TRUE:FALSE;}
BOOL WINAPI close(HANDLE handle) {log("FindVolumeClose");++closes;if(handle!=reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(123)))throw std::invalid_argument("fixture_handle");last_error=number(get(*fixture,"close_error"));return last_error?FALSE:TRUE;}
DWORD WINAPI error() {log("GetLastError");return last_error;}
BOOL WINAPI mounts(LPCWSTR path,LPWCH buffer,DWORD size,PDWORD copied) {
    log("GetVolumePathNamesForVolumeNameW",size);trace.items.back().put("queried_name",n::lossless_name(path));
    const auto& groups=get(*fixture,"mount_replies").items;
    if(current>=groups.size())throw std::invalid_argument("fixture_mounts_missing");const auto& replies=groups[current].items;
    if(mount_calls>=replies.size())throw std::invalid_argument("fixture_mount_reply_missing");const auto& reply=replies[mount_calls++];
    if(const auto throwing=reply.find("throw"))if(flag(*throwing))throw std::runtime_error("injected_callback_exception");
    const auto value=units(get(reply,"units"));std::copy(value.begin(),value.begin()+std::min<std::size_t>(size,value.size()),buffer);
    *copied=number(get(reply,"copied"));last_error=number(get(reply,"error"));return flag(get(reply,"ok"))?TRUE:FALSE;
}
}
namespace disked { namespace nt_fixture {
nt_inventory::VolumeApi api(const json::Value& value,const std::function<void()>& notify) {
    fixture=&value;current=0;calls=0;mount_calls=0;closes=0;last_error=0;trace=json::Value::array();entered=notify;
    nt_inventory::VolumeApi p;p.first=&first;p.next=&next;p.close=&close;p.mounts=&mounts;p.error=&error;return p;
}
unsigned call_count() {return calls;}
unsigned close_count() {return closes;}
json::Value calls_trace() {return trace;}
}}
