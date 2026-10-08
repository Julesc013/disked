#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <sddl.h>
#include "json.h"
#include "sha256.h"
#include <cstring>
#include <cwctype>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

// Private Windows worker capabilities/store utilities; no public ABI.
// Header definitions preserve per-executable test macro isolation.
namespace disked { namespace worker_files {
using json::Value;
inline std::string hash(const std::string& bytes) {
    unsigned char digest[32];disked::sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),digest);
    const char alphabet[]="0123456789abcdef";std::string out;
    for(const auto b:digest) {out+=alphabet[b>>4];out+=alphabet[b&15];}return out;
}
struct Failure : std::runtime_error {
    DWORD platform;
    Failure(const char* code,DWORD error):std::runtime_error(code),platform(error) {}
};
[[noreturn]] inline void fail(const char* code) {
    // Exception construction may allocate. Capture the API's thread-local error
    // before another runtime call can change it.
    const auto error=GetLastError();throw Failure(code,error);
}
struct Handle {
    HANDLE value=INVALID_HANDLE_VALUE;
    Handle()=default;
    explicit Handle(HANDLE h):value(h) {}
    ~Handle() {if(valid())CloseHandle(value);}
    Handle(const Handle&)=delete;
    Handle& operator=(const Handle&)=delete;
    Handle(Handle&& other) noexcept:value(other.value) {other.value=INVALID_HANDLE_VALUE;}
    Handle& operator=(Handle&& other) noexcept {
        if(this!=&other) {if(valid())CloseHandle(value);value=other.value;other.value=INVALID_HANDLE_VALUE;}return *this;
    }
    bool valid() const {return value && value!=INVALID_HANDLE_VALUE;}
};
inline std::string text(const Value& value,const std::string& key) {
    const auto* p=value.find(key);if(!p || p->kind!=Value::Kind::string)fail("operation_record_shape");return p->text;
}
inline std::wstring wide(const std::string& s) {
    if(s.empty() || s.find('\0')!=std::string::npos)fail("operation_path_invalid");
    const int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),nullptr,0);
    if(n<=0)fail("operation_path_invalid");std::wstring out(static_cast<std::size_t>(n),L'\0');
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),&out[0],n))fail("operation_path_invalid");return out;
}
inline std::string narrow(const std::wstring& s) {
    const int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),nullptr,0,nullptr,nullptr);
    if(n<=0)fail("operation_encoding");std::string out(static_cast<std::size_t>(n),'\0');
    if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),&out[0],n,nullptr,nullptr))fail("operation_encoding");return out;
}
template<class T>T symbol(HMODULE module,const char* name) {
    const auto address=GetProcAddress(module,name);if(!address)fail("operation_api_unavailable");
    T result;static_assert(sizeof(result)==sizeof(address),"function pointer size");std::memcpy(&result,&address,sizeof(result));return result;
}
struct Security {
    HMODULE module=nullptr;PSECURITY_DESCRIPTOR descriptor=nullptr;
    SECURITY_ATTRIBUTES attributes{};std::string host_id;
    using Random=BOOLEAN (WINAPI*)(PVOID,ULONG);
    Random random=nullptr;
    Security() {
        module=LoadLibraryExW(L"advapi32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(!module)fail("operation_api_unavailable");
        try {
            const auto open=symbol<decltype(&OpenProcessToken)>(module,"OpenProcessToken");
            const auto info=symbol<decltype(&GetTokenInformation)>(module,"GetTokenInformation");
            const auto sid_string=symbol<decltype(&ConvertSidToStringSidW)>(module,"ConvertSidToStringSidW");
            const auto convert=symbol<decltype(&ConvertStringSecurityDescriptorToSecurityDescriptorW)>(module,"ConvertStringSecurityDescriptorToSecurityDescriptorW");
            random=symbol<Random>(module,"SystemFunction036");
            HANDLE raw=nullptr;if(!open(GetCurrentProcess(),TOKEN_QUERY,&raw))fail("operation_identity_unavailable");Handle token(raw);
            DWORD length=0;info(token.value,TokenUser,nullptr,0,&length);
            if(length==0 || length>65536)fail("operation_identity_unavailable");std::vector<unsigned char> buffer(length);
            if(!info(token.value,TokenUser,buffer.data(),length,&length))fail("operation_identity_unavailable");
            LPWSTR sid=nullptr;if(!sid_string(reinterpret_cast<TOKEN_USER*>(buffer.data())->User.Sid,&sid))fail("operation_identity_unavailable");
            const std::wstring sid_text(sid);LocalFree(sid);
            wchar_t computer[MAX_COMPUTERNAME_LENGTH+1]{};DWORD size=MAX_COMPUTERNAME_LENGTH+1;
            if(!GetComputerNameW(computer,&size))fail("operation_identity_unavailable");
            host_id=hash(narrow(sid_text)+"\n"+narrow(computer));
            const auto sddl=L"D:P(A;;FA;;;"+sid_text+L")";
            if(!convert(sddl.c_str(),SDDL_REVISION_1,&descriptor,nullptr))fail("operation_acl_unavailable");
            attributes.nLength=sizeof(attributes);attributes.lpSecurityDescriptor=descriptor;attributes.bInheritHandle=FALSE;
        } catch(...) {if(descriptor)LocalFree(descriptor);FreeLibrary(module);module=nullptr;throw;}
    }
    ~Security() {if(descriptor)LocalFree(descriptor);if(module)FreeLibrary(module);}
    std::string identity(const std::string& prefix) const {
        unsigned char bytes[16];if(!random(bytes,16))fail("operation_random_unavailable");
        const char* digits="0123456789abcdef";std::string out=prefix;
        for(const auto b:bytes) {out.push_back(digits[b>>4]);out.push_back(digits[b&15]);}return out;
    }
};
inline std::uint64_t file_time(const FILETIME& time) {return (static_cast<std::uint64_t>(time.dwHighDateTime)<<32)|time.dwLowDateTime;}
inline std::string process_created(HANDLE process) {
    FILETIME created{},exit{},kernel{},user{};
    if(!GetProcessTimes(process,&created,&exit,&kernel,&user))fail("operation_process_identity_unavailable");return std::to_string(file_time(created));
}
inline BY_HANDLE_FILE_INFORMATION file_info(HANDLE file) {
    BY_HANDLE_FILE_INFORMATION info{};
    if(GetFileType(file)!=FILE_TYPE_DISK || !GetFileInformationByHandle(file,&info) || (info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))fail("operation_file_type");return info;
}
inline std::string file_identity(HANDLE file) {
    const auto info=file_info(file);return std::to_string(info.dwVolumeSerialNumber)+":"+
        std::to_string((static_cast<std::uint64_t>(info.nFileIndexHigh)<<32)|info.nFileIndexLow);
}
inline std::uint64_t file_size(HANDLE file) {
    LARGE_INTEGER size{};if(!GetFileSizeEx(file,&size) || size.QuadPart<0)fail("operation_file_size");return static_cast<std::uint64_t>(size.QuadPart);
}
inline std::string read_file(HANDLE file,std::size_t limit) {
    const auto size=file_size(file);if(size>limit)fail("operation_history_limit");
    LARGE_INTEGER zero{};if(!SetFilePointerEx(file,zero,nullptr,FILE_BEGIN))fail("operation_file_seek");
    std::string bytes(static_cast<std::size_t>(size),'\0');DWORD done=0;
    if(size && (!ReadFile(file,&bytes[0],static_cast<DWORD>(size),&done,nullptr) || done!=size))fail("operation_file_read");return bytes;
}
inline void write_file(HANDLE file,const std::string& bytes,const char* point) {
#ifdef DISKED_WORKER_TEST_STORE_FAULTS
    // Only the separate fault executable reads this control. Exercise ordinary
    // disposable file boundaries without filling a host volume or using media.
    char selected[128]{};const auto count=GetEnvironmentVariableA("DISKED_TEST_STORE_FAULT",selected,sizeof(selected));
    const auto size=std::strlen(point);const char* mode="";
    if(count>size && count<sizeof(selected) && std::strncmp(selected,point,size)==0 && selected[size]=='.')mode=selected+size+1;
    if(std::strcmp(mode,"full")==0) {SetLastError(ERROR_DISK_FULL);fail("operation_file_write");}
    if(std::strcmp(mode,"short")==0) {
        DWORD prefix=0;
        if(!WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()/2),&prefix,nullptr))fail("operation_file_write");
        SetLastError(ERROR_DISK_FULL);fail("operation_file_write");
    }
#else
    (void)point;
#endif
    DWORD done=0;if(!WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&done,nullptr))fail("operation_file_write");
    if(done!=bytes.size()) {SetLastError(ERROR_WRITE_FAULT);fail("operation_file_write");}
#ifdef DISKED_WORKER_TEST_STORE_FAULTS
    if(std::strcmp(mode,"flush")==0) {SetLastError(ERROR_DISK_FULL);fail("operation_file_flush");}
#endif
    if(!FlushFileBuffers(file))fail("operation_file_flush");
}
inline std::wstring final_path(HANDLE file) {
    wchar_t path[1024];const auto size=GetFinalPathNameByHandleW(file,path,1024,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
    if(!size || size>=1024)fail("operation_file_path");return std::wstring(path,size);
}
struct Directory {
    std::wstring path;std::vector<Handle> pinned;std::string identity;
    explicit Directory(const std::string& input):path(wide(input)) {
        if(path.size()<3 || path.size()>240 || !((path[0]>=L'A' && path[0]<=L'Z') || (path[0]>=L'a' && path[0]<=L'z')) ||
           path[1]!=L':' || path[2]!=L'\\')fail("operation_path_invalid");
        if(path.size()>3 && path.back()==L'\\')path.pop_back();
        for(std::size_t i=3;i<path.size();++i)if(path[i]<32 || path[i]==L':' || path[i]==L'/' || path[i]==L'*' || path[i]==L'?' || path[i]==L'"' || path[i]==L'<' || path[i]==L'>' || path[i]==L'|')fail("operation_path_invalid");
        if(GetDriveTypeW(path.substr(0,3).c_str())!=DRIVE_FIXED)fail("operation_directory_not_local");
        std::size_t start=3;
        for(std::size_t end=3;end<=path.size();++end) {
            if(end<path.size() && path[end]!=L'\\')continue;
            if(end>3) {
                const auto part=path.substr(start,end-start);
                if(part.empty() || part==L"." || part==L".." || part.back()==L'.' || part.back()==L' ')fail("operation_path_invalid");
                start=end+1;
            }
            auto handle=Handle(CreateFileW(path.substr(0,end).c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,
                OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
            if(!handle.valid())fail("operation_directory_unavailable");
            if(!(file_info(handle.value).dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY))fail("operation_directory_unavailable");
            pinned.push_back(std::move(handle));
        }
        identity=file_identity(pinned.back().value);
    }
    std::wstring child(const wchar_t* name) const {return path+(path.back()==L'\\'?L"":L"\\")+name;}
    Handle open(const wchar_t* name,DWORD access,DWORD share,DWORD creation,SECURITY_ATTRIBUTES* security=nullptr) const {
        Handle file(CreateFileW(child(name).c_str(),access,share,security,creation,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
        if(!file.valid())return file;
        const auto info=file_info(file.value);
        if((info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) || info.nNumberOfLinks!=1)fail("operation_file_type");return file;
    }
    void empty() const {
        WIN32_FIND_DATAW data{};const auto search=FindFirstFileW(child(L"*").c_str(),&data);
        if(search==INVALID_HANDLE_VALUE)fail("operation_directory_unavailable");bool found=false;
        do {if(std::wcscmp(data.cFileName,L".") && std::wcscmp(data.cFileName,L"..")) {found=true;break;}}while(FindNextFileW(search,&data));
        const auto error=GetLastError();FindClose(search);
        if(found)fail("operation_directory_not_empty");if(error!=ERROR_NO_MORE_FILES)fail("operation_directory_unavailable");
    }
};
struct Image {
    std::wstring path;Handle file;std::string digest;
    Image() {
        wchar_t buffer[32768];const auto size=GetModuleFileNameW(nullptr,buffer,32768);
        if(!size || size>=32768)fail("operation_image_unavailable");path.assign(buffer,size);
        file=Handle(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
        if(!file.valid() || (file_info(file.value).dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY))fail("operation_image_unavailable");
        digest=hash(read_file(file.value,33554432));
    }
};
inline Handle inherited(HANDLE source,DWORD access) {
    HANDLE copy=nullptr;if(!DuplicateHandle(GetCurrentProcess(),source,GetCurrentProcess(),&copy,access,TRUE,0))fail("operation_handle_duplicate");return Handle(copy);
}
struct AttributeList {
    std::vector<unsigned char> buffer;LPPROC_THREAD_ATTRIBUTE_LIST list=nullptr;
    AttributeList(std::vector<HANDLE>& handles,std::vector<HANDLE>& jobs) {
        SIZE_T bytes=0;InitializeProcThreadAttributeList(nullptr,2,0,&bytes);buffer.resize(bytes);
        list=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(buffer.data());
        if(!InitializeProcThreadAttributeList(list,2,0,&bytes)) {list=nullptr;fail("operation_spawn_attributes");}
        if(!UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,handles.data(),handles.size()*sizeof(HANDLE),nullptr,nullptr) ||
           !UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_JOB_LIST,jobs.data(),jobs.size()*sizeof(HANDLE),nullptr,nullptr)) {
            DeleteProcThreadAttributeList(list);list=nullptr;fail("operation_spawn_attributes");
        }
    }
    ~AttributeList() {if(list)DeleteProcThreadAttributeList(list);}
};
struct WorkerBudget {
    Handle job;
    explicit WorkerBudget(const Security& security,bool create) {
        const auto name=L"Local\\DiskEd.Fake.Workers.v1."+wide(security.host_id);
        auto attributes=security.attributes;
        SetLastError(ERROR_SUCCESS);
        job=Handle(create?CreateJobObjectW(&attributes,name.c_str()):OpenJobObjectW(JOB_OBJECT_QUERY,FALSE,name.c_str()));
        const auto error=GetLastError();if(!job.valid())fail("operation_worker_budget_unavailable");
        const DWORD flags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY|JOB_OBJECT_LIMIT_JOB_MEMORY;
        if(create && error!=ERROR_ALREADY_EXISTS) {
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=flags;
            limits.BasicLimitInformation.ActiveProcessLimit=4;limits.ProcessMemoryLimit=128*1024*1024;limits.JobMemoryLimit=512*1024*1024;
            if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("operation_worker_budget_unavailable");
        }
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        if(!QueryInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits),nullptr) ||
           limits.BasicLimitInformation.LimitFlags!=flags || limits.BasicLimitInformation.ActiveProcessLimit!=4 ||
           limits.ProcessMemoryLimit!=128*1024*1024 || limits.JobMemoryLimit!=512*1024*1024)fail("operation_worker_budget_mismatch");
        if(!create) {
            BOOL member=FALSE;
            if(!IsProcessInJob(GetCurrentProcess(),job.value,&member) || !member)fail("operation_worker_budget_mismatch");
        }
    }
};
inline HANDLE argument_handle(const wchar_t* argument) {
    if(!argument || !*argument)fail("operation_role_arguments");
    const std::wstring s(argument);for(const auto c:s)if(c<L'0' || c>L'9')fail("operation_role_arguments");
    const auto number=std::stoull(s);if(number==0 || number==~static_cast<std::uintptr_t>(0))fail("operation_role_arguments");
    const auto handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(number));DWORD flags=0;
    if(!GetHandleInformation(handle,&flags) || !(flags&HANDLE_FLAG_INHERIT))fail("operation_role_capability");return handle;
}
}}
