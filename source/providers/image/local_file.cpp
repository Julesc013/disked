#include "local_file.h"
#include <algorithm>

namespace disked { namespace local_file {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code,DWORD platform=0) {throw Error(code,platform);}
std::string hex(const unsigned char* p,std::size_t size) {
    const char alphabet[]="0123456789abcdef";std::string out;
    for(std::size_t i=0;i<size;++i) {out+=alphabet[p[i]>>4];out+=alphabet[p[i]&15];}return out;
}
V exact(std::uint64_t n) {return V::string(std::to_string(n));}
}
std::string utf8(const std::wstring& s) {
    const auto n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),nullptr,0,nullptr,nullptr);
    if(!n)fail("image_path_encoding",GetLastError());std::string out(static_cast<std::size_t>(n),'\0');
    if(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),&out[0],n,nullptr,nullptr)!=n)fail("image_path_encoding",GetLastError());
    return out;
}
std::wstring wide(const std::string& s) {
    if(s.empty() || s.size()>960 || s.find('\0')!=std::string::npos)fail("image_path_profile");
    const auto n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),nullptr,0);
    if(n<=0)fail("image_path_encoding",GetLastError());if(n>240)fail("image_path_profile");
    std::wstring out(static_cast<std::size_t>(n),L'\0');
    if(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),&out[0],n)!=n)fail("image_path_encoding",GetLastError());
    return out;
}
bool letter(wchar_t c) {return (c>=L'A' && c<=L'Z') || (c>=L'a' && c<=L'z');}
void component(const std::wstring& s) {
    if(s.empty() || s==L"." || s==L"..")return;
    if(s.back()==L'.' || s.back()==L' ')fail("image_path_profile");
    for(const auto c:s)if(c<32 || c==127 || c==L':' || c==L'*' || c==L'?' || c==L'"' || c==L'<' || c==L'>' || c==L'|')fail("image_path_profile");
    auto base=s.substr(0,s.find(L'.'));
    while(!base.empty() && base.back()==L' ')base.pop_back();
    for(auto& c:base)if(c>=L'a' && c<=L'z')c=static_cast<wchar_t>(c-L'a'+L'A');
    if(base==L"CON" || base==L"PRN" || base==L"AUX" || base==L"NUL" || base==L"CONIN$" || base==L"CONOUT$")fail("image_path_profile");
    if(base.size()==4 && (base.substr(0,3)==L"COM" || base.substr(0,3)==L"LPT") &&
       ((base[3]>=L'1' && base[3]<=L'9') || base[3]==0x00b9 || base[3]==0x00b2 || base[3]==0x00b3))fail("image_path_profile");
}
void components(const std::wstring& s,std::size_t start) {
    while(start<s.size()) {const auto end=s.find(L'\\',start);component(s.substr(start,end==s.npos?s.npos:end-start));if(end==s.npos)break;start=end+1;}
}
std::wstring path_for(const std::string& input) {
    auto s=wide(input);std::replace(s.begin(),s.end(),L'/',L'\\');
    if(s[0]==L'\\')fail("image_path_profile");
    const bool drive=s.size()>=2 && s[1]==L':';
    if(drive && (s.size()<3 || !letter(s[0]) || s[2]!=L'\\'))fail("image_path_profile");
    components(s,drive?3:0);
    wchar_t buffer[241];const auto n=GetFullPathNameW(s.c_str(),241,buffer,nullptr);
    if(!n)fail("image_path_resolve",GetLastError());if(n>240)fail("image_path_profile");
    s.assign(buffer,n);
    if(s.size()<3 || !letter(s[0]) || s[1]!=L':' || s[2]!=L'\\')fail("image_path_profile");
    components(s,3);
    if(GetDriveTypeW(s.substr(0,3).c_str())!=DRIVE_FIXED)fail("image_local_drive_required");
    return s;
}
BY_HANDLE_FILE_INFORMATION ordinary(HANDLE h,bool directory) {
    if(GetFileType(h)!=FILE_TYPE_DISK)fail("image_file_type");
    BY_HANDLE_FILE_INFORMATION info{};
    if(!GetFileInformationByHandle(h,&info))fail("image_file_metadata",GetLastError());
    if(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)fail("image_reparse_source");
    if(((info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)!=0)!=directory)fail("image_file_type");
    if(!directory && info.nNumberOfLinks!=1)fail("image_file_aliases");
    // Refuse data that may invoke recall/tiering in this ordinary-local profile.
    if(info.dwFileAttributes&(FILE_ATTRIBUTE_OFFLINE|0x00040000U|0x00400000U))fail("image_offline_source");
    return info;
}
void bind_path(HANDLE h,const std::wstring& expected) {
    wchar_t buffer[245];const auto size=GetFinalPathNameByHandleW(h,buffer,245,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
    if(!size)fail("image_path_identity",GetLastError());
    if(size>=245)fail("image_path_profile");
    const std::wstring final(buffer,size);
    if(final.compare(0,4,L"\\\\?\\")!=0 || final.size()!=expected.size()+4 ||
       CompareStringOrdinal(final.data()+4,static_cast<int>(final.size()-4),expected.data(),static_cast<int>(expected.size()),TRUE)!=CSTR_EQUAL)
        fail("image_path_identity");
}
Metadata metadata(HANDLE h) {
    const auto info=ordinary(h,false);FILE_ID_INFO id{};FILE_BASIC_INFO basic{};FILE_STANDARD_INFO standard{};
    if(!GetFileInformationByHandleEx(h,FileIdInfo,&id,sizeof(id)) ||
       !GetFileInformationByHandleEx(h,FileBasicInfo,&basic,sizeof(basic)) ||
       !GetFileInformationByHandleEx(h,FileStandardInfo,&standard,sizeof(standard)))fail("image_file_metadata",GetLastError());
    if(standard.EndOfFile.QuadPart<0 || standard.Directory || standard.DeletePending)fail("image_file_metadata");
    Metadata out;out.size=static_cast<std::uint64_t>(standard.EndOfFile.QuadPart);
    out.value=V::object().put("volume_id",exact(id.VolumeSerialNumber)).put("file_id",V::string(hex(id.FileId.Identifier,16)))
        .put("bytes",exact(out.size)).put("created",V::string(std::to_string(basic.CreationTime.QuadPart)))
        .put("written",V::string(std::to_string(basic.LastWriteTime.QuadPart))).put("changed",V::string(std::to_string(basic.ChangeTime.QuadPart)))
        .put("attributes",exact(basic.FileAttributes)).put("hardlinks",exact(info.nNumberOfLinks));
    return out;
}

std::vector<Handle> pin_parents(const std::wstring& path) {
    std::vector<Handle> out;std::size_t end=2;
    for(;;) {
        const auto parent=end==2?path.substr(0,3):path.substr(0,end);
        // Metadata-only access did not enforce delete sharing on the tested
        // host. Require list/read access and deny write/delete sharing.
        Handle h(CreateFileW(parent.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
        if(h.value==INVALID_HANDLE_VALUE)fail("image_parent_open",GetLastError());ordinary(h.value,true);bind_path(h.value,parent);out.push_back(std::move(h));
        end=path.find(L'\\',end+1);if(end==path.npos)break;
    }
    return out;
}
json::Value parent_generations(const std::vector<Handle>& handles) {
    auto out=V::array();for(const auto& h:handles)out.items.push_back(generation(h.value,true));return out;
}
void check_parents(const std::wstring& path,const std::vector<Handle>& handles,const V& expected) {
    if(expected.kind!=V::Kind::array || expected.items.size()!=handles.size() || handles.empty())fail("image_parent_shape");
    std::size_t end=2;
    for(std::size_t i=0;i<handles.size();++i) {
        const auto parent=end==2?path.substr(0,3):path.substr(0,end);ordinary(handles[i].value,true);bind_path(handles[i].value,parent);
        if(json::dump(generation(handles[i].value,true))!=json::dump(expected.items[i]))fail("image_parent_changed");
        end=path.find(L'\\',end+1);
        if((i+1==handles.size())!=(end==path.npos))fail("image_parent_shape");
    }
}
json::Value generation(HANDLE h,bool directory) {
    ordinary(h,directory);FILE_ID_INFO id{};FILE_BASIC_INFO basic{};FILE_STANDARD_INFO standard{};
    if(!GetFileInformationByHandleEx(h,FileIdInfo,&id,sizeof(id)) ||
       !GetFileInformationByHandleEx(h,FileBasicInfo,&basic,sizeof(basic)) ||
       !GetFileInformationByHandleEx(h,FileStandardInfo,&standard,sizeof(standard)))fail("image_file_metadata",GetLastError());
    if(standard.DeletePending || (standard.Directory!=FALSE)!=directory)fail("image_file_metadata");
    return V::object().put("volume_id",exact(id.VolumeSerialNumber)).put("file_id",V::string(hex(id.FileId.Identifier,16)))
        .put("created",V::string(std::to_string(basic.CreationTime.QuadPart)));
}
}}
