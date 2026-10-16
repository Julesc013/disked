#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <string>
#include <vector>
namespace disked { namespace nt_inventory {
// Exact documented API seam. One owner serializes calls. Injected replies are
// qualification fixtures, not OS observations or an admitted provider.
struct VolumeApi {
    decltype(&::FindFirstVolumeW) first=nullptr;
    decltype(&::FindNextVolumeW) next=nullptr;
    decltype(&::FindVolumeClose) close=nullptr;
    decltype(&::GetVolumePathNamesForVolumeNameW) mounts=nullptr;
    decltype(&::GetLastError) error=nullptr;
};
VolumeApi native_volume_api();
struct NameObservation {std::string state;DWORD error=0;std::wstring name;};
struct MountObservation {std::string state;DWORD error=0;std::vector<std::wstring> paths;std::size_t units=0;};
struct CloseObservation {std::string state="not_open";DWORD error=0;};
class VolumeCursor final {
    VolumeApi api_;HANDLE handle_=INVALID_HANDLE_VALUE;bool started_=false,closed_=false;
    std::wstring current_;CloseObservation close_;
    NameObservation read_name(bool first);
public:
    explicit VolumeCursor(const VolumeApi&);
    ~VolumeCursor();
    VolumeCursor(const VolumeCursor&)=delete;
    VolumeCursor& operator=(const VolumeCursor&)=delete;
    NameObservation first();
    NameObservation next();
    MountObservation mounts(std::size_t unit_budget,std::size_t path_budget);
    CloseObservation close();
    bool native_binding() const;
};
}}
