#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <sddl.h>
#include "fake_worker.h"
#include "worker_files.h"
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
using namespace worker_files;
const char* const worker_failures[]={"operation_role_arguments","operation_role_capability","operation_role_standard_handle",
    "operation_bootstrap_limit","operation_bootstrap_read","operation_request_invalid","operation_image_mismatch",
    "operation_binding_shape","operation_binding_value","operation_process_identity","operation_file_type","operation_file_size",
    "operation_file_path","operation_api_unavailable","operation_identity_unavailable","operation_acl_unavailable",
    "operation_file_read","operation_file_seek","operation_file_write","operation_file_flush","operation_admission_signal",
    "operation_process_identity_unavailable","operation_image_unavailable","operation_record_shape","operation_cancel_invalid"};
int worker_exit(const std::string& code) {
    for(std::size_t i=0;i<sizeof(worker_failures)/sizeof(*worker_failures);++i)if(code==worker_failures[i])return static_cast<int>(100+i);return 199;
}
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
Outcome inspect(const std::string& request,const Directory& directory,const Value& header,const std::string& expected,op::History* retained=nullptr) {
    const auto id=text(header,"operation_id");if(id!=expected)fail("operation_identity_mismatch");
#ifdef DISKED_WORKER_TEST_RESULT_READ_DELAY
    // Test-only file-boundary stall. It is not a claim of a real hung driver.
    // The first inspection in this client waits after admission; later requests
    // can reconcile its exact store without another injected delay.
    static bool delayed=false;if(!delayed) {delayed=true;Sleep(6500);}
#endif
    auto value=Value::object().put("scope",Value::string("fake-only")).put("operation_id",Value::string(id));
    try {
        auto file=directory.open(L"operation.records",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid())fail("operation_history_unavailable");auto history=op::read_history(read_file(file.value,op::history_limit));
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
        const bool unresolved=text(history.state,"phase")!="finished" && worker!="running";
        if(retained)*retained=std::move(history);
        if(unresolved)return result(request,id,value,"unknown",6,"operation_worker_unresolved");
        // A successful inspect is a completed read even if the saved operation
        // failed verification. The independent logical/recovery fields persist.
        return result(request,id,value);
    } catch(const std::exception& error) {
        return result(request,id,value,"unknown",6,error.what());
    }
}
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
    // Allocate the immutable identity before claiming the store. From successful
    // exclusive creation onwards, a write/flush failure leaves an unresolved
    // claim and must preserve that identity instead of becoming a fresh refusal.
    const auto id=security.identity("fake-op:"),epoch=security.identity("worker:");
    const auto header=Value::object().put("schema",Value::string("org.disked.fake-operation-request/1"))
        .put("operation_id",Value::string(id)).put("worker_epoch",Value::string(epoch)).put("definition",definition)
        .put("definition_digest",Value::string(op::hash(json::dump(definition))));
    const auto header_bytes=json::dump(header)+"\n";
    auto anchor=directory.open(L"request.json",GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes);
    if(!anchor.valid())fail("operation_admission_contended");
    try {
        write_file(anchor.value,header_bytes,"claim");anchor=Handle();
        auto records=directory.open(L"operation.records",FILE_APPEND_DATA|FILE_READ_ATTRIBUTES,FILE_SHARE_READ,CREATE_NEW,&attributes);
        auto cancel=directory.open(L"cancel.request",GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);
        if(!records.valid() || !cancel.valid())fail("operation_store_create");write_file(cancel.value,"0","cancel_initial");
        Handle event(CreateEventW(&attributes,TRUE,FALSE,nullptr));if(!event.valid())fail("operation_event_create");
        HANDLE read=nullptr,write=nullptr;if(!CreatePipe(&read,&write,&attributes,4096))fail("operation_pipe_create");Handle pipe_read(read),pipe_write(write);
        auto bootstrap=header;bootstrap.put("record_file_id",Value::string(file_identity(records.value)))
            .put("cancel_file_id",Value::string(file_identity(cancel.value)));
        const auto bytes=json::dump(bootstrap);if(bytes.size()>2048)fail("operation_bootstrap_limit");
        DWORD capacity=0;if(!GetNamedPipeInfo(pipe_write.value,nullptr,&capacity,nullptr,nullptr) || capacity<bytes.size())fail("operation_bootstrap_limit");
        DWORD written=0;if(!WriteFile(pipe_write.value,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr) || written!=bytes.size())fail("operation_pipe_write");pipe_write=Handle();
        auto child_pipe=inherited(pipe_read.value,GENERIC_READ);auto child_records=inherited(records.value,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES);
        auto child_cancel=inherited(cancel.value,GENERIC_READ);auto child_event=inherited(event.value,EVENT_MODIFY_STATE|SYNCHRONIZE);
        std::vector<HANDLE> handles={child_pipe.value,child_records.value,child_cancel.value,child_event.value};
        std::wstring command=L"\""+image.path+L"\" __disked_fake_worker";
        for(const auto h:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(h));
        WorkerBudget aggregate(security,true);
        Handle job(CreateJobObjectW(&attributes,nullptr));if(!job.valid())fail("operation_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;
        limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
        if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("operation_job_limits");
        std::vector<HANDLE> jobs={aggregate.job.value,job.value};AttributeList list(handles,jobs);
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=list.list;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
        PROCESS_INFORMATION raw{};
        // Windows 10 assigns the specified jobs as part of process creation.
        // There is no parent-owned suspended child awaiting a later assignment
        // or ResumeThread call if this frontend disconnects during admission.
        if(!CreateProcessW(image.path.c_str(),&command[0],nullptr,nullptr,TRUE,
            DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,directory.path.c_str(),&startup.StartupInfo,&raw))fail("operation_spawn_failed");
        Handle process(raw.hProcess),thread(raw.hThread);
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
    } catch(const Failure& error) {
        auto out=result(request,id,Value::object().put("admission",Value::string("unresolved")),"unknown",6,error.what());
        out.response.fields["diagnostics"].items.back().put("platform_code",Value::string(std::to_string(error.platform)));return out;
    } catch(const std::exception& error) {
        return result(request,id,Value::object().put("admission",Value::string("unresolved")),"unknown",6,error.what());
    }
}

}
bool fake_worker_command(const std::string& command) {
    return command=="plan.simulate" || command=="operation.inspect" || command=="operation.cancel.request" || command=="operation.watch";
}
Outcome watch_fake_worker(const std::string& request,const Value& parameters,const std::shared_ptr<WatchQueue>& events) {
    const auto invalid=validate_watch_parameters(parameters);if(!invalid.empty())return refused(request,invalid);
    std::string id;bool observing=false;
    auto last=Value::object();
    try {
        id=text(parameters,"operation_id");Directory directory(text(parameters,"state_directory"));Security security;
        const auto header=load_request(directory,security);const auto observer=security.identity("watch:");
        if(text(header,"operation_id")!=id)fail("operation_identity_mismatch");observing=true;
        WatchCursor cursor(id,request,observer,parameters);auto collected=Value::array();Value last_state;
        const auto* follow=parameters.find("follow_ms");const auto end=GetTickCount64()+(follow?std::stoull(follow->text):0);
        std::size_t bytes=0;Outcome out;
        for(;;) {
            op::History history;out=inspect(request,directory,header,id,&history);
            if(history.count) {
                std::vector<Value> batch;
                try {batch=cursor.project(history);}
                catch(const std::invalid_argument& error) {return refused(request,error.what());}
                for(const auto& item:batch) {
                    json::Limits limit;limit.bytes=16384;const auto size=json::dump(item,limit).size();
                    if(collected.items.size()>=64 || size>1048576-bytes)throw std::invalid_argument("watch_queue_limit");
                    collected.items.push_back(item);bytes+=size;
                    if(events && !events->push(item))return out;
                }
                last_state=history.state;
            }
            auto& value=out.response.fields["result"];
            value.put("events",events?Value::array():collected).put("observer_epoch",Value::string(observer))
                .put("last_sequence",Value::string(cursor.sequence())).put("last_digest",Value::string(cursor.digest()))
                .put("worker_epoch",cursor.worker().empty()?Value{}:Value::string(cursor.worker()));
            if(!history.count && last_state.kind!=Value::Kind::null)value.put("last_validated_state",last_state);
            last=value;
            if(out.exit_code || (history.count && text(history.state,"phase")=="finished"))return out;
            if(GetTickCount64()>=end) {out.response.put("status",Value::string("accepted_running"));out.exit_code=5;return out;}
            Sleep(25);
        }
    } catch(const Failure& error) {
        auto out=observing?result(request,id,last,"unknown",6,error.what()):refused(request,error.what());
        out.response.fields["diagnostics"].items.front().put("platform_code",Value::string(std::to_string(error.platform)));return out;
    } catch(const std::exception& error) {return observing?result(request,id,last,"unknown",6,error.what()):refused(request,error.what());}
}
Outcome dispatch_fake_worker(const std::string& request,const std::string& command,const Value& parameters) {
    try {
        if(!fake_worker_command(command))return refused(request,"command_unavailable",3);
        if(command=="operation.watch")return watch_fake_worker(request,parameters);
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
                LARGE_INTEGER zero{};if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))fail("operation_cancel_unavailable");
                try {write_file(file.value,"1","cancel_request");}
                catch(const Failure& error) {
                    value.put("cancellation_request",Value::string("unresolved"));
                    auto reply=result(request,id,std::move(value),"unknown",6,error.what());
                    reply.response.fields["diagnostics"].items.back().put("platform_code",Value::string(std::to_string(error.platform)));return reply;
                } catch(const std::exception& error) {
                    value.put("cancellation_request",Value::string("unresolved"));
                    return result(request,id,std::move(value),"unknown",6,error.what());
                }
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
        Security security;Image image;WorkerBudget aggregate(security,false);
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
            const auto line=op::record(operation.state(),previous);write_file(records.value,line,operation.state().find("last_event")->text.c_str());previous=json::parse(line).find("digest")->text;
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
#ifdef DISKED_WORKER_TEST_MEMORY_LIMIT
        // Test-only worker: attempt up to 144 MiB of committed allocations under
        // the actual 128 MiB job ceiling. Retain them briefly for external query.
        // No product option or fixture ID enables this fault.
        std::vector<void*> allocations;allocations.reserve(9);DWORD allocation_error=0;
        for(unsigned i=0;i<9;++i) {
            auto* memory=VirtualAlloc(nullptr,16*1024*1024,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
            if(!memory) {allocation_error=GetLastError();break;}
            allocations.push_back(memory);
        }
        Sleep(1500);
        for(auto* memory:allocations)VirtualFree(memory,0,MEM_RELEASE);
        return allocations.size()>=6 && allocations.size()<8 && allocation_error?
            static_cast<int>(allocation_error):211;
#endif
        const auto fixture_id=text(binding,"fixture_id");
        poll(fixture_id=="fake:cancel-checkpoint"?2000:250);if(operation.terminal())return 0;
        advance("dispatch");if(fixture_id=="fake:unknown")return 6;
        poll(500);unsigned counter=0;++counter;advance("observe",std::to_string(counter));
        poll(250);advance("verify");return fixture_id=="fake:verification-failure"?7:0;
    } catch(const std::exception& error) {return worker_exit(error.what());}catch(...) {return 199;}
}
}
