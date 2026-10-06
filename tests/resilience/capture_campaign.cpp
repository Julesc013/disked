// Test-linked producer adapter. No public command, environment option, physical
// resource, filesystem path, shell text or installed provider can select it.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "capture.h"
#include "session.h"
#include "graph.h"
#include <chrono>
#include <algorithm>
#include <cstring>
#include <cwchar>

namespace disked {
using json::Value;
namespace {
struct Handle {
    HANDLE value=nullptr;
    ~Handle() {if(value && value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
};
void checked(BOOL ok) {if(!ok)throw std::runtime_error("campaign_platform_failure");}
struct Budget {
    Handle job;
    Budget() {
        job.value=CreateJobObjectW(nullptr,nullptr);checked(job.value!=nullptr);
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY|JOB_OBJECT_LIMIT_JOB_MEMORY;
        limits.BasicLimitInformation.ActiveProcessLimit=4;limits.ProcessMemoryLimit=64*1024*1024;limits.JobMemoryLimit=256*1024*1024;
        checked(SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)));
    }
};
struct Attributes {
    std::vector<unsigned char> storage;LPPROC_THREAD_ATTRIBUTE_LIST value=nullptr;
    Attributes(HANDLE* handles,HANDLE* jobs) {
        SIZE_T size=0;InitializeProcThreadAttributeList(nullptr,2,0,&size);if(!size || size>65536)throw std::runtime_error("campaign_attribute_limit");
        storage.resize(size);value=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
        checked(InitializeProcThreadAttributeList(value,2,0,&size));
        try {
            checked(UpdateProcThreadAttribute(value,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,handles,sizeof(HANDLE),nullptr,nullptr));
            checked(UpdateProcThreadAttribute(value,0,PROC_THREAD_ATTRIBUTE_JOB_LIST,jobs,2*sizeof(HANDLE),nullptr,nullptr));
        } catch(...) {DeleteProcThreadAttributeList(value);value=nullptr;throw;}
    }
    ~Attributes() {if(value)DeleteProcThreadAttributeList(value);}
};
Value marker(const char* state,const char* reason,const std::string& platform="") {
    return Value::object().put("state",Value::string(state)).put("reason",Value::string(reason)).put("platform",Value::string(platform));
}
Outcome observe(const std::string& id,unsigned fixture,const std::shared_ptr<Budget>& budget) {
    // Own handles and an explicit immutable fixture; never capture a frontend,
    // session or coordinator. The callback outlives a disconnected test client.
    Handle process;
    try {
        wchar_t image[32768]{};const auto n=GetModuleFileNameW(nullptr,image,32768);
        if(!n || n>=32768)throw std::runtime_error("campaign_image_path");
        SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};Handle read,write;
        checked(CreatePipe(&read.value,&write.value,&security,4096));checked(SetHandleInformation(read.value,HANDLE_FLAG_INHERIT,0));
        Handle private_job;private_job.value=CreateJobObjectW(nullptr,nullptr);checked(private_job.value!=nullptr);
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limit{};limit.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;
        limit.BasicLimitInformation.ActiveProcessLimit=1;limit.ProcessMemoryLimit=64*1024*1024;
        checked(SetInformationJobObject(private_job.value,JobObjectExtendedLimitInformation,&limit,sizeof(limit)));
        HANDLE jobs[]={budget->job.value,private_job.value};Attributes attributes(&write.value,jobs);
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;startup.lpAttributeList=attributes.value;
        auto command=L"\""+std::wstring(image)+L"\" __disked_capture_probe "+std::to_wstring(fixture)+L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(write.value));
        PROCESS_INFORMATION info{};
        checked(CreateProcessW(image,&command[0],nullptr,nullptr,TRUE,DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,nullptr,&startup.StartupInfo,&info));
        Handle thread;process.value=info.hProcess;thread.value=info.hThread;CloseHandle(write.value);write.value=nullptr;
        std::string bytes;bytes.reserve(4096);bool malformed=false;
        for(;;) {
            DWORD available=0;
            if(PeekNamedPipe(read.value,nullptr,0,nullptr,&available,nullptr)) {
                if(available) {
                    char block[1024];DWORD got=0;checked(ReadFile(read.value,block,(std::min)(available,DWORD(sizeof(block))),&got,nullptr));
                    if(bytes.size()+got<=4096)bytes.append(block,got);else malformed=true;
                }
            } else if(GetLastError()!=ERROR_BROKEN_PIPE)malformed=true;
            const auto wait=WaitForSingleObject(process.value,10);if(wait==WAIT_FAILED)throw std::runtime_error("campaign_wait");
            if(wait==WAIT_OBJECT_0) {
                // Drain the finite pipe after actual process exit, never infer
                // retirement from the frontend's observation timeout.
                DWORD more=0;if(PeekNamedPipe(read.value,nullptr,0,nullptr,&more,nullptr) && more)continue;break;
            }
        }
        DWORD code=0;checked(GetExitCodeProcess(process.value,&code));
        FILETIME created{},exited{},kernel{},user{};checked(GetProcessTimes(process.value,&created,&exited,&kernel,&user));
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION own_limits{},all_limits{};BOOL own_member=FALSE,all_member=FALSE;
        checked(QueryInformationJobObject(private_job.value,JobObjectExtendedLimitInformation,&own_limits,sizeof(own_limits),nullptr));
        checked(QueryInformationJobObject(budget->job.value,JobObjectExtendedLimitInformation,&all_limits,sizeof(all_limits),nullptr));
        checked(IsProcessInJob(process.value,private_job.value,&own_member));checked(IsProcessInJob(process.value,budget->job.value,&all_member));
        auto witness=Value::object().put("process_id",Value::string(std::to_string(info.dwProcessId)))
            .put("process_created",Value::string(std::to_string((static_cast<std::uint64_t>(created.dwHighDateTime)<<32)|created.dwLowDateTime)))
            .put("exit_code",Value::string(std::to_string(code))).put("exit_observed",Value::boolean_value(true))
            .put("private_job_member",Value::boolean_value(own_member!=FALSE)).put("aggregate_job_member",Value::boolean_value(all_member!=FALSE))
            .put("private_active_limit",Value::string(std::to_string(own_limits.BasicLimitInformation.ActiveProcessLimit)))
            .put("aggregate_active_limit",Value::string(std::to_string(all_limits.BasicLimitInformation.ActiveProcessLimit)))
            .put("process_memory_limit",Value::string(std::to_string(own_limits.ProcessMemoryLimit)))
            .put("aggregate_memory_limit",Value::string(std::to_string(all_limits.JobMemoryLimit)))
            .put("peak_process_memory",Value::string(std::to_string(own_limits.PeakProcessMemoryUsed)));
        const auto witnessed=[&](Value value) {return completed(id,value.put("witness",witness));};
        if(code)return witnessed(marker("unavailable","provider_exited",std::to_string(code)));
        if(malformed)return witnessed(marker("malformed","provider_frame_limit"));
        try {
            const auto data=json::parse(bytes);const auto expected=fixture==0?"denied":"complete";
            if(data.kind!=Value::Kind::object || data.fields.size()!=1 || !data.find("state") || data.find("state")->kind!=Value::Kind::string || data.find("state")->text!=expected)
                return witnessed(marker("malformed","provider_result_invalid"));
            return witnessed(fixture==0?marker("denied","access_denied","5"):marker("complete",""));
        } catch(const json::Error&) {return witnessed(marker("malformed","provider_result_invalid"));}
    } catch(...) {
        // Losing observation is not retirement. Hold the adapter slot/budget
        // until this exact owned process is actually observed exited. A stuck
        // OS wait remains a stuck callback, never an automatic replacement.
        if(process.value)while(WaitForSingleObject(process.value,50)!=WAIT_OBJECT_0)Sleep(10);
        return completed(id,marker("unavailable","provider_adapter_failure"));
    }
}
struct Pending {
    CaptureKey key;RequestChannel channel;Outcome result;bool received=false,done=false;
};
struct Campaign {
    ObservationCapture capture{{"healthy","denied","malformed","slow","exited"}};
    std::vector<std::unique_ptr<Pending>> pending;
    Value witnesses=Value::object();
    std::chrono::steady_clock::time_point began=std::chrono::steady_clock::now();
    Campaign() {
        const auto key=capture.start("healthy");capture.finish(key,fake_graph());
        const auto budget=std::make_shared<Budget>();const char* names[]={"denied","malformed","slow","exited"};
        for(unsigned i=0;i<4;++i) {
            auto item=std::unique_ptr<Pending>(new Pending());item->key=capture.start(names[i]);const auto id="probe:"+std::string(names[i]);
            const auto submitted=item->channel.submit(id,[id,i,budget] {return observe(id,i,budget);});
            if(!submitted.pending) {capture.fail(item->key,SourceState::Unavailable,"provider_thread_unavailable");item->done=true;}
            pending.push_back(std::move(item));
        }
    }
    std::shared_ptr<const GraphInput> poll() {
        for(auto& item:pending)if(!item->done) {
            // Retain the exact completion across throwing graph/witness work.
            // Taking it from the channel is not acknowledgement by the reducer.
            if(!item->received)item->received=item->channel.poll(item->result);
            if(item->received) {
                const auto& out=item->result;
                const auto* result=out.response.find("result");
                if(result && result->find("witness"))witnesses.put(item->key.source,*result->find("witness"));
                if(out.exit_code || !result || !result->find("state"))capture.fail(item->key,SourceState::Unavailable,"provider_adapter_failure");
                else {
                    const auto state=result->find("state")->text;
                    if(state=="complete") {
                        GraphInput content;content.nodes.push_back({"fake:late@1","block-device","fixture:late","1","Late valid observation","current","8192",{}});
                        capture.finish(item->key,content);
                    } else capture.fail(item->key,state=="denied"?SourceState::Denied:state=="malformed"?SourceState::Malformed:SourceState::Unavailable,
                        result->find("reason")->text,result->find("platform")->text);
                }
                item->done=true;
            } else if(std::chrono::steady_clock::now()-began>=std::chrono::milliseconds(400))capture.timeout(item->key);
        }
        const auto current=capture.snapshot();return std::shared_ptr<const GraphInput>(current,&current->graph);
    }
};
std::weak_ptr<Campaign> current_campaign;
LONG WINAPI crash(EXCEPTION_POINTERS* info) {
    TerminateProcess(GetCurrentProcess(),info->ExceptionRecord->ExceptionCode);return EXCEPTION_EXECUTE_HANDLER;
}
}
std::unique_ptr<FrontendSession> capture_campaign_session(const Registry& registry) {
    auto campaign=std::make_shared<Campaign>();
    current_campaign=campaign;
    return std::unique_ptr<FrontendSession>(new FrontendSession(registry,campaign->capture.snapshot()->graph,
        [campaign]() {return campaign->poll();}));
}
Value capture_campaign_report() {
    const auto campaign=current_campaign.lock();if(!campaign)return Value{};
    campaign->poll();const auto snapshot=campaign->capture.snapshot();auto states=Value::array();
    for(const auto& source:snapshot->sources)states.items.push_back(Value::object().put("id",Value::string(source.id))
        .put("state",Value::string(source_state_name(source.state))).put("outstanding",Value::boolean_value(source.outstanding))
        .put("capture_epoch",Value::string(std::to_string(source.attempt.capture))).put("worker_epoch",Value::string(std::to_string(source.attempt.worker))));
    return Value::object().put("schema",Value::string("org.disked.capture-campaign-test/1"))
        .put("sequence",Value::string(std::to_string(snapshot->sequence))).put("sources",states).put("witnesses",campaign->witnesses);
}
int run_capture_campaign_producer(int argc,wchar_t** argv) {
    if(argc!=4 || std::wcslen(argv[2])!=1 || argv[2][0]<L'0' || argv[2][0]>L'3')return 210;
    try {
        const std::wstring raw=argv[3];if(raw.empty() || raw.find_first_not_of(L"0123456789")!=std::wstring::npos)return 211;
        Handle output;output.value=reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(std::stoull(raw)));
        DWORD flags=0;if(!GetHandleInformation(output.value,&flags) || !(flags&HANDLE_FLAG_INHERIT) || GetFileType(output.value)!=FILE_TYPE_PIPE)return 212;
        checked(SetHandleInformation(output.value,HANDLE_FLAG_INHERIT,0));
        const auto fixture=argv[2][0]-L'0';
        if(fixture==3) {SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetUnhandledExceptionFilter(crash);RaiseException(0xE000D17D,EXCEPTION_NONCONTINUABLE,0,nullptr);return 213;}
        if(fixture==2)Sleep(1800);
        const char* bytes=fixture==0?"{\"state\":\"denied\"}":fixture==1?"{invalid":"{\"state\":\"complete\"}";
        DWORD wrote=0;const auto length=static_cast<DWORD>(std::strlen(bytes));checked(WriteFile(output.value,bytes,length,&wrote,nullptr));return wrote==length?0:214;
    } catch(...) {return 215;}
}
}
