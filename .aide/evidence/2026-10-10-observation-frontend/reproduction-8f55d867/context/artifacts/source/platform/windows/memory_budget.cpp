#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <sddl.h>
#include <cstring>
#include <cwchar>
#include "memory_budget.h"

namespace disked {
namespace {
struct Handle {HANDLE value=nullptr;~Handle() {if(value)CloseHandle(value);}};
struct Module {HMODULE value=nullptr;~Module() {if(value)FreeLibrary(value);}};
struct Local {void* value=nullptr;~Local() {if(value)LocalFree(value);}};
struct Lock {
    HANDLE mutex=nullptr;bool owned=false;
    ~Lock() {if(owned)ReleaseMutex(mutex);}
};
template<class T> T symbol(HMODULE module,const char* name) noexcept {
    const auto address=GetProcAddress(module,name);T result;
    static_assert(sizeof(result)==sizeof(address),"function pointer size");
    std::memcpy(&result,&address,sizeof(result));return result;
}
}
WindowsMemoryBudget::WindowsMemoryBudget() noexcept {
    // This bounded OS-identity/bootstrap work precedes budget assignment. It
    // opens no paths and initializes no provider, GUI, service or network.
    Module api;api.value=LoadLibraryExW(L"advapi32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!api.value) {platform_=GetLastError();return;}
    const auto open=symbol<decltype(&OpenProcessToken)>(api.value,"OpenProcessToken");
    const auto info=symbol<decltype(&GetTokenInformation)>(api.value,"GetTokenInformation");
    const auto to_sid=symbol<decltype(&ConvertSidToStringSidW)>(api.value,"ConvertSidToStringSidW");
    const auto descriptor=symbol<decltype(&ConvertStringSecurityDescriptorToSecurityDescriptorW)>(api.value,"ConvertStringSecurityDescriptorToSecurityDescriptorW");
    if(!open || !info || !to_sid || !descriptor) {platform_=ERROR_PROC_NOT_FOUND;return;}
    Handle token;if(!open(GetCurrentProcess(),TOKEN_QUERY,&token.value)) {platform_=GetLastError();return;}
    alignas(TOKEN_USER) unsigned char user[1024]{};DWORD needed=0;
    if(!info(token.value,TokenUser,user,sizeof(user),&needed)) {platform_=GetLastError();return;}
    Local sid;LPWSTR raw_sid=nullptr;
    if(!to_sid(reinterpret_cast<TOKEN_USER*>(user)->User.Sid,&raw_sid)) {platform_=GetLastError();return;}
    sid.value=raw_sid;
    wchar_t name[256]{},mutex_name[256]{},sddl[256]{};
#ifdef DISKED_FRONTEND_MEMORY_TESTING
    const wchar_t* prefix=L"Local\\DiskEd.Fake.Memory.Test.v1.";
#else
    const wchar_t* prefix=L"Local\\DiskEd.Fake.Memory.v1.";
#endif
    if(swprintf_s(name,L"%ls%ls",prefix,raw_sid)<0 || swprintf_s(mutex_name,L"%lsInit.%ls",prefix,raw_sid)<0 ||
       swprintf_s(sddl,L"D:P(A;;GA;;;%ls)",raw_sid)<0) {platform_=ERROR_INSUFFICIENT_BUFFER;return;}
    Local security;PSECURITY_DESCRIPTOR raw_security=nullptr;
    if(!descriptor(sddl,SDDL_REVISION_1,&raw_security,nullptr)) {platform_=GetLastError();return;}
    security.value=raw_security;SECURITY_ATTRIBUTES attributes{sizeof(attributes),raw_security,FALSE};
    Handle mutex;mutex.value=CreateMutexW(&attributes,FALSE,mutex_name);
    if(!mutex.value) {platform_=GetLastError();return;}
    Lock lock;lock.mutex=mutex.value;
    const auto waited=WaitForSingleObject(mutex.value,250);
    if(waited!=WAIT_OBJECT_0 && waited!=WAIT_ABANDONED) {
        error_=waited==WAIT_TIMEOUT?"memory_budget_busy":"memory_budget_unavailable";
        platform_=waited==WAIT_TIMEOUT?WAIT_TIMEOUT:GetLastError();return;
    }
    lock.owned=true;SetLastError(ERROR_SUCCESS);
    job_=CreateJobObjectW(&attributes,name);const auto created=GetLastError();
    if(!job_) {platform_=created;return;}
    constexpr SIZE_T limit=static_cast<SIZE_T>(limit_bytes());JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    if(created!=ERROR_ALREADY_EXISTS) {
        limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_PROCESS_MEMORY;limits.ProcessMemoryLimit=limit;
        if(!SetInformationJobObject(job_,JobObjectExtendedLimitInformation,&limits,sizeof(limits))) {platform_=GetLastError();return;}
    }
    if(!QueryInformationJobObject(job_,JobObjectExtendedLimitInformation,&limits,sizeof(limits),nullptr)) {platform_=GetLastError();return;}
    if(limits.BasicLimitInformation.LimitFlags!=JOB_OBJECT_LIMIT_PROCESS_MEMORY || limits.ProcessMemoryLimit!=limit) {
        error_="memory_budget_mismatch";platform_=ERROR_INVALID_DATA;return;
    }
    if(!AssignProcessToJobObject(job_,GetCurrentProcess())) {
        error_="memory_budget_incompatible";platform_=GetLastError();return;
    }
    error_=nullptr;
    // Release initialization before any test delay/pressure. The product has no
    // control that can select the private test namespace or allocation probe.
    if(!ReleaseMutex(mutex.value)) {error_="memory_budget_unavailable";platform_=GetLastError();return;}
    lock.owned=false;
#ifdef DISKED_FRONTEND_MEMORY_TESTING
    char mode[32]{};const auto count=GetEnvironmentVariableA("DISKED_TEST_MEMORY_FAULT",mode,sizeof(mode));
    if(count && count<sizeof(mode) && std::strcmp(mode,"allocate")==0) {
        void* allocations[17]{};unsigned allocated=0;
        for(;allocated<17;++allocated) {
            allocations[allocated]=VirtualAlloc(nullptr,16*1024*1024,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
            if(!allocations[allocated]) {platform_=GetLastError();break;}
        }
        probe_bytes_=static_cast<std::uint64_t>(allocated)*16*1024*1024;
        Sleep(1200);
        for(unsigned i=0;i<allocated;++i)VirtualFree(allocations[i],0,MEM_RELEASE);
        error_=allocated<17?"memory_budget_unavailable":"memory_budget_probe_failed";
    }
#endif
}
WindowsMemoryBudget::~WindowsMemoryBudget() {if(job_)CloseHandle(job_);}
}
