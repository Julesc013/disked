#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winioctl.h>
#include "json.h"
#include <functional>
#include <vector>

namespace disked { namespace nt_inventory {
struct StorageQueryApi {decltype(&::DeviceIoControl) ioctl=nullptr;decltype(&::GetLastError) error=nullptr;};
StorageQueryApi native_storage_query_api();
struct StorageQueryPolicy {DWORD descriptor_bytes=4096,string_bytes=256,extents=64;};
// Borrowed synchronous handle, never opened, closed, selected by disk number or
// granted authority here. The selected fixture port rejects any native pointer.
class StorageQueryPort final {
    struct Packet {std::vector<unsigned char> bytes;DWORD returned=0,error=0,code=0;bool ok=false,property=false;STORAGE_PROPERTY_ID property_id=StorageDeviceProperty;std::string state;};
    StorageQueryApi api_;HANDLE handle_;StorageQueryPolicy policy_;std::function<bool()> stop_;
    bool unresolved_=false;bool used_[8]{};
    Packet call(DWORD,DWORD,bool property=false,STORAGE_PROPERTY_ID id=StorageDeviceProperty);void begin(unsigned);
    json::Value result(const char*,const std::string&,const std::vector<Packet>&,json::Value data={}) const;
public:
    StorageQueryPort(const StorageQueryApi&,HANDLE,const StorageQueryPolicy&,std::function<bool()> stop={});
    StorageQueryPort(const StorageQueryPort&)=delete;StorageQueryPort& operator=(const StorageQueryPort&)=delete;
    json::Value descriptor();json::Value device_number();json::Value geometry();json::Value length();json::Value extents();
    // Separate private identity/layout profile; not dispatched by StorageFrame.
    json::Value identifiers();json::Value alignment();json::Value layout();
    bool unresolved() const {return unresolved_;}
};
json::Limits storage_observation_limits();
}}
