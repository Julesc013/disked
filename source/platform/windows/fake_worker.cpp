#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <sddl.h>
#include "fake_worker.h"
#include "fake_operation.h"
#include "bootstrap_registry.h"
#include "bootstrap.h"
#include <algorithm>
#include <cstring>
#include <cwctype>
#include <memory>
#include <stdexcept>
#include <vector>

namespace disked {
namespace op=fake_operation;
using json::Value;
namespace {
const char* const worker_failures[]={"operation_role_arguments","operation_role_capability","operation_role_standard_handle",
    "operation_bootstrap_limit","operation_bootstrap_read","operation_request_invalid","operation_image_mismatch",
    "operation_binding_shape","operation_binding_value","operation_process_identity","operation_file_type","operation_file_size",
    "operation_file_path","operation_api_unavailable","operation_identity_unavailable","operation_acl_unavailable",
    "operation_file_read","operation_file_seek","operation_file_write","operation_file_flush","operation_admission_signal",
    "operation_process_identity_unavailable","operation_image_unavailable","operation_record_shape","operation_cancel_invalid"};
int worker_exit(const std::string& code) {
    for(std::size_t i=0;i<sizeof(worker_failures)/sizeof(*worker_failures);++i)if(code==worker_failures[i])return static_cast<int>(100+i);return 199;
}
struct Failure : std::runtime_error {
    DWORD platform;
    explicit Failure(const char* code):std::runtime_error(code),platform(GetLastError()) {}
};
[[noreturn]] void fail(const char* code) {throw Failure(code);}
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
std::string text(const Value& value,const std::string& key) {
    const auto* p=value.find(key);if(!p || p->kind!=Value::Kind::string)fail("operation_record_shape");return p->text;
}
std::wstring wide(const std::string& s) {
    if(s.empty() || s.find('\0')!=std::string::npos)fail("operation_path_invalid");
    const int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),nullptr,0);
    if(n<=0)fail("operation_path_invalid");std::wstring out(static_cast<std::size_t>(n),L'\0');
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),static_cast<int>(s.size()),&out[0],n))fail("operation_path_invalid");return out;
}
std::string narrow(const std::wstring& s) {
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
            host_id=op::hash(narrow(sid_text)+"\n"+narrow(computer));
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
std::uint64_t file_time(const FILETIME& time) {return (static_cast<std::uint64_t>(time.dwHighDateTime)<<32)|time.dwLowDateTime;}
std::string process_created(HANDLE process) {
    FILETIME created{},exit{},kernel{},user{};
    if(!GetProcessTimes(process,&created,&exit,&kernel,&user))fail("operation_process_identity_unavailable");return std::to_string(file_time(created));
}
BY_HANDLE_FILE_INFORMATION file_info(HANDLE file) {
    BY_HANDLE_FILE_INFORMATION info{};
    if(GetFileType(file)!=FILE_TYPE_DISK || !GetFileInformationByHandle(file,&info) || (info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))fail("operation_file_type");return info;
}
std::string file_identity(HANDLE file) {
    const auto info=file_info(file);return std::to_string(info.dwVolumeSerialNumber)+":"+
        std::to_string((static_cast<std::uint64_t>(info.nFileIndexHigh)<<32)|info.nFileIndexLow);
}
std::uint64_t file_size(HANDLE file) {
    LARGE_INTEGER size{};if(!GetFileSizeEx(file,&size) || size.QuadPart<0)fail("operation_file_size");return static_cast<std::uint64_t>(size.QuadPart);
}
std::string read_file(HANDLE file,std::size_t limit) {
    const auto size=file_size(file);if(size>limit)fail("operation_history_limit");
    LARGE_INTEGER zero{};if(!SetFilePointerEx(file,zero,nullptr,FILE_BEGIN))fail("operation_file_seek");
    std::string bytes(static_cast<std::size_t>(size),'\0');DWORD done=0;
    if(size && (!ReadFile(file,&bytes[0],static_cast<DWORD>(size),&done,nullptr) || done!=size))fail("operation_file_read");return bytes;
}
void write_file(HANDLE file,const std::string& bytes) {
    DWORD done=0;if(!WriteFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&done,nullptr) || done!=bytes.size())fail("operation_file_write");
    if(!FlushFileBuffers(file))fail("operation_file_flush");
}
std::wstring final_path(HANDLE file) {
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
        digest=op::hash(read_file(file.value,33554432));
    }
};
Value request_definition(const std::string& fixture,const Security& security,const Image& image,const Directory& directory) {
    return Value::object().put("fixture_id",Value::string(fixture)).put("host_id",Value::string(security.host_id))
        .put("source_revision",Value::string(bootstrap::source_revision)).put("input_digest",Value::string(bootstrap::input_digest))
        .put("image_digest",Value::string(image.digest)).put("provider_id",Value::string(fake_provider_identity()))
        .put("target_profile",Value::string(bootstrap::target)).put("directory_id",Value::string(directory.identity));
}
Value load_request(const Directory& directory,const Security& security) {
    auto file=directory.open(L"request.json",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
    if(!file.valid())fail("operation_request_unavailable");const auto value=json::parse(read_file(file.value,8192));
    if(value.kind!=Value::Kind::object || value.fields.size()!=5 || text(value,"schema")!="org.disked.fake-operation-request/1" ||
       !value.find("definition") || value.find("definition")->fields.size()!=8)fail("operation_request_invalid");
    const auto& definition=*value.find("definition");
    if(text(definition,"host_id")!=security.host_id || text(definition,"directory_id")!=directory.identity)fail("operation_host_mismatch");
    if(text(value,"definition_digest")!=op::hash(json::dump(definition)))fail("operation_request_invalid");
    // Binding validation below checks the remaining identity shapes without relying
    // on current build applicability to read historical evidence.
    auto binding=definition;binding.fields.erase("directory_id");
    binding.put("operation_id",Value::string(text(value,"operation_id"))).put("worker_epoch",Value::string(text(value,"worker_epoch")))
        .put("attempt_id",Value::string(text(value,"operation_id")+":attempt:1"))
        .put("process_id",Value::string("1")).put("process_created",Value::string("1"));
    op::validate_binding(binding);return value;
}
Outcome result(const std::string& request,const std::string& id,Value value,const std::string& status="completed",int code=0,const std::string& diagnostic_code="") {
    auto out=completed(request,std::move(value));out.exit_code=code;
    out.response.put("status",Value::string(status)).put("operation_id",Value::string(id));
    if(!diagnostic_code.empty())out.response.fields["diagnostics"].items.push_back(diagnostic(diagnostic_code));return out;
}
Outcome inspect(const std::string& request,const Directory& directory,const Value& header,const std::string& expected) {
    const auto id=text(header,"operation_id");if(id!=expected)fail("operation_identity_mismatch");
    auto value=Value::object().put("scope",Value::string("fake-only")).put("operation_id",Value::string(id));
    try {
        auto file=directory.open(L"operation.records",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid())fail("operation_history_unavailable");const auto history=op::read_history(read_file(file.value,op::history_limit));
        const auto& binding=*history.state.find("binding");const auto& definition=*header.find("definition");
        for(const auto& field:definition.fields)if(field.first!="directory_id" && text(binding,field.first)!=field.second.text)fail("operation_identity_mismatch");
        if(text(binding,"operation_id")!=id || text(binding,"worker_epoch")!=text(header,"worker_epoch"))fail("operation_identity_mismatch");
        value.put("state",history.state).put("last_record_digest",Value::string(history.digest));
        std::string worker="unavailable";const auto pid=static_cast<DWORD>(std::stoul(text(binding,"process_id")));
        Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid));
        if(process.valid()) {
            if(process_created(process.value)!=text(binding,"process_created"))worker="reused_identity";
            else {const auto wait=WaitForSingleObject(process.value,0);worker=wait==WAIT_TIMEOUT?"running":wait==WAIT_OBJECT_0?"exited":"unavailable";}
        } else if(GetLastError()==ERROR_INVALID_PARAMETER)worker="exited";
        value.put("worker_observation",Value::string(worker));
        if(text(history.state,"phase")!="finished" && worker!="running")return result(request,id,value,"unknown",6,"operation_worker_unresolved");
        // A successful inspect is a completed read even if the saved operation
        // failed verification. The independent logical/recovery fields persist.
        return result(request,id,value);
    } catch(const std::exception& error) {
        return result(request,id,value,"unknown",6,error.what());
    }
}
Handle inherited(HANDLE source,DWORD access) {
    HANDLE copy=nullptr;if(!DuplicateHandle(GetCurrentProcess(),source,GetCurrentProcess(),&copy,access,TRUE,0))fail("operation_handle_duplicate");return Handle(copy);
}
struct AttributeList {
    std::vector<unsigned char> buffer;LPPROC_THREAD_ATTRIBUTE_LIST list=nullptr;
    explicit AttributeList(std::vector<HANDLE>& handles) {
        SIZE_T bytes=0;InitializeProcThreadAttributeList(nullptr,1,0,&bytes);buffer.resize(bytes);
        list=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(buffer.data());
        if(!InitializeProcThreadAttributeList(list,1,0,&bytes)) {list=nullptr;fail("operation_spawn_attributes");}
        if(!UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,handles.data(),handles.size()*sizeof(HANDLE),nullptr,nullptr)) {
            DeleteProcThreadAttributeList(list);list=nullptr;fail("operation_spawn_attributes");
        }
    }
    ~AttributeList() {if(list)DeleteProcThreadAttributeList(list);}
};
Outcome start(const std::string& request,const std::string& fixture_id,const Directory& directory,const Security& security) {
    Image image;const auto definition=request_definition(fixture_id,security,image,directory);
    auto prior=directory.open(L"request.json",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
    if(prior.valid()) {
        prior=Handle();Value header;
        try {header=load_request(directory,security);}
        catch(const std::exception&) {
            auto out=completed(request,Value::object().put("admission",Value::string("unresolved")));
            out.response.put("status",Value::string("unknown"));out.exit_code=6;
            out.response.fields["diagnostics"].items.push_back(diagnostic("operation_existing_claim_unreadable"));return out;
        }
        if(json::dump(*header.find("definition"))!=json::dump(definition))return refused(request,"idempotency_conflict");
        auto out=inspect(request,directory,header,text(header,"operation_id"));out.response.fields["result"].put("admission",Value::string("existing"));return out;
    }
    if(GetLastError()!=ERROR_FILE_NOT_FOUND)fail("operation_request_unavailable");
    directory.empty();auto attributes=security.attributes;
    auto anchor=directory.open(L"request.json",GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes);
    if(!anchor.valid())fail("operation_admission_contended");
    const auto id=security.identity("fake-op:"),epoch=security.identity("worker:");
    const auto header=Value::object().put("schema",Value::string("org.disked.fake-operation-request/1"))
        .put("operation_id",Value::string(id)).put("worker_epoch",Value::string(epoch)).put("definition",definition)
        .put("definition_digest",Value::string(op::hash(json::dump(definition))));
    // The immutable identity precedes process creation. Once written, any uncertain
    // admission stays inspectable and is never retried as another operation.
    write_file(anchor.value,json::dump(header)+"\n");anchor=Handle();
    try {
        auto records=directory.open(L"operation.records",FILE_APPEND_DATA|FILE_READ_ATTRIBUTES,FILE_SHARE_READ,CREATE_NEW,&attributes);
        auto cancel=directory.open(L"cancel.request",GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);
        if(!records.valid() || !cancel.valid())fail("operation_store_create");write_file(cancel.value,"0");
        Handle event(CreateEventW(&attributes,TRUE,FALSE,nullptr));if(!event.valid())fail("operation_event_create");
        HANDLE read=nullptr,write=nullptr;if(!CreatePipe(&read,&write,&attributes,4096))fail("operation_pipe_create");Handle pipe_read(read),pipe_write(write);
        auto bootstrap=header;bootstrap.put("record_file_id",Value::string(file_identity(records.value)))
            .put("cancel_file_id",Value::string(file_identity(cancel.value)));
        const auto bytes=json::dump(bootstrap);if(bytes.size()>2048)fail("operation_bootstrap_limit");
        DWORD capacity=0;if(!GetNamedPipeInfo(pipe_write.value,nullptr,&capacity,nullptr,nullptr) || capacity<bytes.size())fail("operation_bootstrap_limit");
        DWORD written=0;if(!WriteFile(pipe_write.value,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr) || written!=bytes.size())fail("operation_pipe_write");pipe_write=Handle();
        auto child_pipe=inherited(pipe_read.value,GENERIC_READ);auto child_records=inherited(records.value,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES);
        auto child_cancel=inherited(cancel.value,GENERIC_READ);auto child_event=inherited(event.value,EVENT_MODIFY_STATE|SYNCHRONIZE);
        std::vector<HANDLE> handles={child_pipe.value,child_records.value,child_cancel.value,child_event.value};AttributeList list(handles);
        std::wstring command=L"\""+image.path+L"\" __disked_fake_worker";
        for(const auto h:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(h));
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=list.list;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
        Handle job(CreateJobObjectW(&attributes,nullptr));if(!job.valid())fail("operation_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;
        limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
        if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("operation_job_limits");
        PROCESS_INFORMATION raw{};
        if(!CreateProcessW(image.path.c_str(),&command[0],nullptr,nullptr,TRUE,
            CREATE_NO_WINDOW|CREATE_SUSPENDED|EXTENDED_STARTUPINFO_PRESENT,nullptr,nullptr,&startup.StartupInfo,&raw))fail("operation_spawn_failed");
        Handle process(raw.hProcess),thread(raw.hThread);
        if(!AssignProcessToJobObject(job.value,process.value) || ResumeThread(thread.value)==static_cast<DWORD>(-1)) {
            // This child has never run its entrypoint. No uncertain effect is killed.
            TerminateProcess(process.value,4);WaitForSingleObject(process.value,3000);fail("operation_spawn_prepared_failed");
        }
        child_pipe=Handle();child_records=Handle();child_cancel=Handle();child_event=Handle();pipe_read=Handle();records=Handle();cancel=Handle();
        HANDLE waits[]={event.value,process.value};const auto wait=WaitForMultipleObjects(2,waits,FALSE,3000);
        if(wait!=WAIT_OBJECT_0) {
            auto value=Value::object().put("admission",Value::string("unresolved"));
            if(wait==WAIT_OBJECT_0+1) {
                DWORD exit_code=0;if(GetExitCodeProcess(process.value,&exit_code)) {
                    value.put("worker_exit",Value::string(std::to_string(exit_code)));
                    if(exit_code>=100 && exit_code<100+sizeof(worker_failures)/sizeof(*worker_failures))value.put("worker_refusal",Value::string(worker_failures[exit_code-100]));
                }
            }
            return result(request,id,value,"unknown",6,"operation_admission_unresolved");
        }
        auto out=inspect(request,directory,header,id);
        if(out.exit_code)return out;
        out.response.fields["result"].put("admission",Value::string("new"));
        if(text(*out.response.find("result")->find("state"),"phase")=="finished")return out;
        out.response.put("status",Value::string("accepted_running"));out.exit_code=5;
        return out;
    } catch(const std::exception& error) {
        return result(request,id,Value::object().put("admission",Value::string("unresolved")),"unknown",6,error.what());
    }
}
HANDLE argument_handle(const wchar_t* argument) {
    if(!argument || !*argument)fail("operation_role_arguments");
    const std::wstring s(argument);for(const auto c:s)if(c<L'0' || c>L'9')fail("operation_role_arguments");
    const auto number=std::stoull(s);if(number==0 || number==~static_cast<std::uintptr_t>(0))fail("operation_role_arguments");
    const auto handle=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(number));DWORD flags=0;
    if(!GetHandleInformation(handle,&flags) || !(flags&HANDLE_FLAG_INHERIT))fail("operation_role_capability");return handle;
}
}
bool fake_worker_command(const std::string& command) {
    return command=="plan.simulate" || command=="operation.inspect" || command=="operation.cancel.request";
}
Outcome dispatch_fake_worker(const std::string& request,const std::string& command,const Value& parameters) {
    try {
        if(!fake_worker_command(command))return refused(request,"command_unavailable",3);
        if(command=="plan.simulate" && !op::fixture(text(parameters,"fixture_id")))return refused(request,"invalid_parameter");
        Directory directory(text(parameters,"state_directory"));Security security;
        if(command=="plan.simulate")return start(request,text(parameters,"fixture_id"),directory,security);
        const auto header=load_request(directory,security);const auto id=text(parameters,"operation_id");
        auto out=inspect(request,directory,header,id);
        if(command=="operation.cancel.request" && out.exit_code==0) {
            auto& value=out.response.fields["result"];const auto* state=value.find("state");
            if(!state || text(*state,"phase")=="finished")value.put("cancellation_request",Value::string("too_late"));
            else {
                auto file=directory.open(L"cancel.request",GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
                if(!file.valid() || file_size(file.value)!=1)fail("operation_cancel_unavailable");
                const auto byte=read_file(file.value,1);if(byte!="0" && byte!="1")fail("operation_cancel_invalid");
                LARGE_INTEGER zero{};if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))fail("operation_cancel_unavailable");write_file(file.value,"1");
                value.put("cancellation_request",Value::string("requested"));
            }
        }
        return out;
    } catch(const Failure& error) {
        auto out=refused(request,error.what());out.response.fields["diagnostics"].items.front().put("platform_code",Value::string(std::to_string(error.platform)));return out;
    } catch(const std::exception& error) {return refused(request,error.what());}
}
int run_fake_worker(int argc,wchar_t** argv) {
    try {
        if(argc!=6)fail("operation_role_arguments");
        std::vector<HANDLE> capabilities;for(int i=2;i<6;++i)capabilities.push_back(argument_handle(argv[i]));
        for(std::size_t i=0;i<capabilities.size();++i)for(std::size_t j=0;j<i;++j)if(capabilities[i]==capabilities[j])fail("operation_role_capability");
        Handle pipe(capabilities[0]),records(capabilities[1]),cancel(capabilities[2]),event(capabilities[3]);
        for(const auto h:capabilities)if(!SetHandleInformation(h,HANDLE_FLAG_INHERIT,0))fail("operation_role_capability");
        for(const auto channel:{STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE}) {
            // The CRT can replace an absent standard channel with its -2
            // sentinel. Refuse usable handles, not invalid sentinel values.
            const auto h=GetStdHandle(channel);DWORD flags=0;
            if(h && h!=INVALID_HANDLE_VALUE && GetHandleInformation(h,&flags))fail("operation_role_standard_handle");
        }
        if(GetFileType(pipe.value)!=FILE_TYPE_PIPE || WaitForSingleObject(event.value,0)!=WAIT_TIMEOUT ||
           file_size(records.value)!=0 || file_size(cancel.value)!=1)fail("operation_role_capability");
        if((file_info(records.value).dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) || (file_info(cancel.value).dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY))fail("operation_role_capability");
        const auto record_path=final_path(records.value),cancel_path=final_path(cancel.value);
        const auto slash=record_path.find_last_of(L'\\');
        if(record_path.substr(slash+1)!=L"operation.records" || cancel_path!=record_path.substr(0,slash+1)+L"cancel.request")fail("operation_role_capability");
        DWORD available=0;if(!PeekNamedPipe(pipe.value,nullptr,0,nullptr,&available,nullptr) || available==0 || available>2048)fail("operation_bootstrap_limit");
        std::string bytes(available,'\0');DWORD read=0;
        if(!ReadFile(pipe.value,&bytes[0],available,&read,nullptr) || read!=available)fail("operation_bootstrap_read");pipe=Handle();
        const auto header=json::parse(bytes);
        if(header.fields.size()!=7 || text(header,"schema")!="org.disked.fake-operation-request/1" ||
           text(header,"record_file_id")!=file_identity(records.value) || text(header,"cancel_file_id")!=file_identity(cancel.value))fail("operation_role_capability");
        const auto* definition=header.find("definition");if(!definition || definition->fields.size()!=8 ||
            op::hash(json::dump(*definition))!=text(header,"definition_digest"))fail("operation_request_invalid");
        Security security;Image image;
        if(text(*definition,"source_revision")!=bootstrap::source_revision || text(*definition,"input_digest")!=bootstrap::input_digest ||
           text(*definition,"image_digest")!=image.digest || text(*definition,"host_id")!=security.host_id)fail("operation_image_mismatch");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION budget{};
        if(!QueryInformationJobObject(nullptr,JobObjectExtendedLimitInformation,&budget,sizeof(budget),nullptr) ||
           budget.BasicLimitInformation.ActiveProcessLimit!=1 || budget.ProcessMemoryLimit!=128*1024*1024 ||
           (budget.BasicLimitInformation.LimitFlags&(JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY))!=
               (JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY) ||
           (budget.BasicLimitInformation.LimitFlags&JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE))fail("operation_role_capability");
        auto binding=*definition;binding.fields.erase("directory_id");
        binding.put("operation_id",Value::string(text(header,"operation_id"))).put("worker_epoch",Value::string(text(header,"worker_epoch")))
            .put("attempt_id",Value::string(text(header,"operation_id")+":attempt:1"))
            .put("process_id",Value::string(std::to_string(GetCurrentProcessId())))
            .put("process_created",Value::string(process_created(GetCurrentProcess())));
        op::Operation operation(binding);const auto from=op::origin(binding);std::string previous(64,'0');std::size_t count=0;
        auto save=[&]() {
            if(++count>op::record_count_limit || file_size(records.value)>op::history_limit-op::record_limit)fail("operation_history_limit");
            const auto line=op::record(operation.state(),previous);write_file(records.value,line);previous=json::parse(line).find("digest")->text;
        };
        auto advance=[&](const std::string& action,const std::string& observed="") {if(operation.advance(action,from,observed))save();};
        auto poll=[&](DWORD duration) {
            const auto end=GetTickCount64()+duration;
            do {
                const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")fail("operation_cancel_invalid");
                if(flag=="1")advance("cancel");advance("checkpoint");
                if(operation.terminal())return;
                if(GetTickCount64()>=end)break;Sleep(20);
            }while(true);
        };
        // Exercise the same admitted provider initialization boundary as other
        // fake commands. The guard executable proves essential commands avoid it.
#ifdef DISKED_WORKER_TEST_ADMISSION_DELAY
        // Separate test executable only; no product flag accepts this behaviour.
        Sleep(5000);
#endif
        initialize_fake_provider();
        save();advance("prepare");if(!SetEvent(event.value))fail("operation_admission_signal");event=Handle();
        const auto fixture_id=text(binding,"fixture_id");
        poll(fixture_id=="fake:cancel-checkpoint"?2000:250);if(operation.terminal())return 0;
        advance("dispatch");if(fixture_id=="fake:unknown")return 6;
        poll(500);unsigned counter=0;++counter;advance("observe",std::to_string(counter));
        poll(250);advance("verify");return fixture_id=="fake:verification-failure"?7:0;
    } catch(const std::exception& error) {return worker_exit(error.what());}catch(...) {return 199;}
}
}
