#include "volume_namespace.h"
#include <algorithm>
#include <iterator>
#include <stdexcept>
namespace disked { namespace nt_inventory {
namespace {
std::string failure(DWORD error) {return error==ERROR_ACCESS_DENIED?"denied":"unavailable";}
MountObservation bad(const char* state,DWORD code=0) {MountObservation result;result.state=state;result.error=code;return result;}
}
VolumeApi native_volume_api() {VolumeApi api;api.first=&FindFirstVolumeW;api.next=&FindNextVolumeW;api.close=&FindVolumeClose;api.mounts=&GetVolumePathNamesForVolumeNameW;api.error=&GetLastError;return api;}
VolumeCursor::VolumeCursor(const VolumeApi& api):api_(api) {
    if(!api.first || !api.next || !api.close || !api.mounts || !api.error)throw std::invalid_argument("nt_volume_api_missing");
}
VolumeCursor::~VolumeCursor() {if(!closed_)try {close();}catch(...) {} }
NameObservation VolumeCursor::read_name(bool begin) {
    wchar_t buffer[64];std::fill(std::begin(buffer),std::end(buffer),static_cast<wchar_t>(0xffff));
    bool found;
    if(begin) {started_=true;handle_=api_.first(buffer,64);found=handle_!=INVALID_HANDLE_VALUE;}
    else found=api_.next(handle_,buffer,64)!=FALSE;
    if(!found) {const DWORD error=api_.error();current_.clear();return {error==ERROR_NO_MORE_FILES?"exhausted":failure(error),error,{}};}
    const auto end=std::find(std::begin(buffer),std::end(buffer),L'\0');
    if(end==std::end(buffer)) {current_.clear();return {"malformed",0,{}};}
    current_.assign(buffer,end);return {"present",0,current_};
}
NameObservation VolumeCursor::first() {
    if(started_ || closed_)throw std::invalid_argument("nt_volume_cursor_reuse");return read_name(true);
}
NameObservation VolumeCursor::next() {
    if(!started_ || closed_ || handle_==INVALID_HANDLE_VALUE || current_.empty())throw std::invalid_argument("nt_volume_cursor_state");return read_name(false);
}
MountObservation VolumeCursor::mounts(std::size_t budget,std::size_t count_budget) {
    if(!started_ || closed_ || handle_==INVALID_HANDLE_VALUE || current_.empty())throw std::invalid_argument("nt_volume_cursor_state");
    if(!budget || budget>4096 || !count_budget || count_budget>32)throw std::invalid_argument("nt_volume_mount_budget");
    std::vector<wchar_t> buffer(std::min<std::size_t>(128,budget),static_cast<wchar_t>(0xffff));DWORD copied=0;
    if(!api_.mounts(current_.c_str(),buffer.data(),static_cast<DWORD>(buffer.size()),&copied)) {
        const DWORD error=api_.error();
        if(error!=ERROR_MORE_DATA)return bad(failure(error).c_str(),error);
        if(copied<=buffer.size())return bad("malformed",error);
        if(copied>budget)return bad("budget_exhausted",error);
        buffer.assign(copied,static_cast<wchar_t>(0xffff));copied=0;
        if(!api_.mounts(current_.c_str(),buffer.data(),static_cast<DWORD>(buffer.size()),&copied)) {
            const DWORD again=api_.error();return bad(again==ERROR_MORE_DATA?"changed":failure(again).c_str(),again);
        }
    }
    if(!copied || copied>buffer.size() || buffer[copied-1]!=L'\0')return bad("malformed");
    MountObservation result;result.state="observed";result.units=copied;
    std::size_t at=0;
    while(at<copied) {
        if(buffer[at]==L'\0') {
            if(at==0 && (copied==1 || (copied==2 && buffer[1]==L'\0')))return result;
            if(at==copied-1 && !result.paths.empty())return result;
            return bad("malformed");
        }
        const auto end=std::find(buffer.begin()+at,buffer.begin()+copied,L'\0');
        if(end==buffer.begin()+copied)return bad("malformed");
        const auto length=static_cast<std::size_t>(end-(buffer.begin()+at));
        if(length>256 || result.paths.size()>=count_budget)return bad("budget_exhausted");
        result.paths.emplace_back(buffer.data()+at,length);at+=length+1;
    }
    return bad("malformed"); // Nonempty MULTI_SZ requires its additional NUL.
}
CloseObservation VolumeCursor::close() {
    if(closed_)return close_;closed_=true;
    if(handle_==INVALID_HANDLE_VALUE)return close_;
    // A failed close is uncertain. Do not retry from destruction/reuse.
    close_.state="uncertain";
    try {if(api_.close(handle_))close_.state="closed";else close_.error=api_.error();}catch(...) {} return close_;
}
bool VolumeCursor::native_binding() const {
    const auto selected=native_volume_api();return api_.first==selected.first && api_.next==selected.next && api_.close==selected.close && api_.mounts==selected.mounts && api_.error==selected.error;
}
}}
