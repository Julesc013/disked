// Private qualification fixture over actual production store helpers.
// Only supplied owned ordinary directories are opened; no storage enumeration.
#include "platform/windows/worker_files.h"
#include <aclapi.h>
#include <cstdio>

int wmain(int argc,wchar_t** argv) {
    using namespace disked::worker_files;
    try {
        if(argc!=4)return 2;
        Handle token;HANDLE raw=nullptr;
        if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&raw))fail("probe_token");
        token=Handle(raw);DWORD bytes=0;
        GetTokenInformation(token.value,TokenUser,nullptr,0,&bytes);
        if(!bytes || bytes>65536)fail("probe_token");
        std::vector<unsigned char> buffer(bytes);
        if(!GetTokenInformation(token.value,TokenUser,buffer.data(),bytes,&bytes))fail("probe_token");
        LPWSTR sid=nullptr;
        if(!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(buffer.data())->User.Sid,&sid))fail("probe_sid");
        const std::wstring subject(sid);LocalFree(sid);
        if(subject!=argv[2] || !IsTokenRestricted(token.value))return 3;
        DWORD elevated=1,container=1;
        if(!GetTokenInformation(token.value,TokenElevation,&elevated,sizeof(elevated),&bytes) ||
           !GetTokenInformation(token.value,TokenIsAppContainer,&container,sizeof(container),&bytes) || elevated || container)return 3;
        Security security;
        const auto random=security.identity("probe-");
        if(random.size()!=38)return 3;
        WorkerBudget lease(security,true);
        WorkerBudget reopened(security,false,lease.job.value,lease.guard.value);
        Image image;
        Directory directory(narrow(argv[1]));
        bool created=false;
        {
            auto file=directory.open(L"record.bin",GENERIC_READ|GENERIC_WRITE,0,CREATE_NEW,&security.attributes,&created);
            if(!file.valid() || !created)fail("probe_record_create");
            write_file(file.value,"one","probe");
        }
        auto file=directory.open(L"record.bin",GENERIC_READ|GENERIC_WRITE,0,OPEN_EXISTING);
        if(!file.valid())fail("probe_record_reopen");
        write_file(file.value,"TWO","probe");
        const auto contents=read_file(file.value,3);
        if(contents!="TWO")return 3;
        PSECURITY_DESCRIPTOR descriptor=nullptr;
        const auto error=GetSecurityInfo(file.value,SE_FILE_OBJECT,DACL_SECURITY_INFORMATION,nullptr,nullptr,nullptr,nullptr,&descriptor);
        if(error)throw Failure("probe_record_security",error);
        LPWSTR text=nullptr;
        if(!ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor,1,DACL_SECURITY_INFORMATION,&text,nullptr)) {
            const auto platform=GetLastError();LocalFree(descriptor);throw Failure("probe_record_security",platform);
        }
        const std::wstring actual(text),expected=L"D:P(A;;FA;;;"+subject+L")";
        LocalFree(text);LocalFree(descriptor);
        if(actual!=expected)return 3;
        SetLastError(0);
        const auto outside=CreateFileW(argv[3],GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        const auto outside_error=GetLastError();
        if(outside!=INVALID_HANDLE_VALUE) {CloseHandle(outside);DeleteFileW(argv[3]);return 3;}
        if(outside_error!=ERROR_ACCESS_DENIED)return 3;
        auto result=Value::object().put("status",Value::string("pass"))
            .put("user_sid",Value::string(narrow(subject)))
            .put("restricted",Value::boolean_value(true))
            .put("elevated",Value::number(std::to_string(elevated)))
            .put("appcontainer",Value::number(std::to_string(container)))
            .put("pointer_bits",Value::number(std::to_string(sizeof(void*)*8)))
            .put("msc_full_ver",Value::number(std::to_string(_MSC_FULL_VER)))
            .put("record_sddl",Value::string(narrow(actual)))
            .put("record_sha256",Value::string(hash(contents)))
            .put("self_sha256",Value::string(image.digest))
            .put("outside_error",Value::number(std::to_string(outside_error)))
            .put("lease_reopened",Value::boolean_value(true));
        std::puts(disked::json::dump(result).c_str());return 0;
    } catch(const Failure& error) {
        std::fprintf(stderr,"%s platform=%lu\n",error.what(),static_cast<unsigned long>(error.platform));return 3;
    } catch(const std::exception& error) {std::fprintf(stderr,"%s\n",error.what());return 3;}
}
