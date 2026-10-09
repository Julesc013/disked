#include "volume_inventory.h"
#include <algorithm>
#include <cstdio>
#include <iterator>
#include <stdexcept>
#include <io.h>
#include <fcntl.h>
namespace {
using V=disked::json::Value;namespace n=disked::nt_inventory;
const V* fixture=nullptr;std::size_t current=0;unsigned calls=0,mount_calls=0,closes=0;DWORD last_error=0;
V trace=V::array();
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
HANDLE WINAPI first(LPWSTR buffer,DWORD size) {log("FindFirstVolumeW",size);current=0;return name(buffer,size)?reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(123)):INVALID_HANDLE_VALUE;}
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
int main(int argc,char** argv) {
    if(_setmode(_fileno(stdin),_O_BINARY)<0 || _setmode(_fileno(stdout),_O_BINARY)<0)return 7;
    if(argc==2 && std::string(argv[1])=="--binding") {
        n::VolumeCursor cursor(n::native_volume_api());std::printf("{\"schema\":\"org.disked.nt-volume-binding-fixture/1\",\"native_table_bound\":true,\"queries\":0,\"pointer_bytes\":%u,\"live_namespace_qualified\":false}\n",static_cast<unsigned>(sizeof(void*)));return cursor.native_binding()?0:1;
    }
    if(argc!=1)return 2;
    try {
        char bytes[65536];const auto count=std::fread(bytes,1,sizeof(bytes),stdin);if(!count || count==sizeof(bytes) || std::ferror(stdin))return 2;
        auto fixture_limits=disked::json::Limits{};fixture_limits.bytes=65535;fixture_limits.values=16384;fixture_limits.depth=24;
        const auto value=disked::json::parse(std::string(bytes,count),fixture_limits);fixture=&value;
        n::VolumeApi api;api.first=&first;api.next=&next;api.close=&close;api.mounts=&mounts;api.error=&error;
        n::VolumeCursor cursor(api);n::InventoryPolicy policy;
        policy.volumes=number(get(value,"volume_limit"));policy.mounts=number(get(value,"mount_limit"));policy.mount_units=number(get(value,"unit_limit"));policy.include_mounts=flag(get(value,"include_mounts"));
        const auto epoch=get(value,"capture_epoch");if(epoch.kind!=V::Kind::string || !disked::json::decimal_u64(epoch.text))throw std::invalid_argument("fixture_epoch");
        const auto cancel_at=number(get(value,"cancel_after_calls"));
        const auto snapshot=n::collect_volume_namespace(cursor,std::stoull(epoch.text),policy,[cancel_at] {return cancel_at!=0xffffffffUL && calls>=cancel_at;});
        const auto closed_again=cursor.close();const auto before_reuse=calls;bool reuse_refused=false;
        try {cursor.first();}catch(const std::invalid_argument&) {reuse_refused=true;}
        auto out=V::object().put("qualification",V::string("injected-win32-api-not-native-storage")).put("snapshot",snapshot).put("trace",trace)
            .put("close_calls",V::string(std::to_string(closes))).put("repeat_close_state",V::string(closed_again.state)).put("reuse_refused",V::boolean_value(reuse_refused && calls==before_reuse));
        std::puts(disked::json::dump(out,n::volume_inventory_limits()).c_str());return 0;
    }catch(const std::exception& error) {
        const auto out=V::object().put("status",V::string("refused")).put("reason",V::string(error.what())).put("api_calls",V::string(std::to_string(calls)));
        std::puts(disked::json::dump(out).c_str());return 3;
    }
}
