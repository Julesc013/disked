#include "report_worker.h"
#include "file_acquisition_export.h"
#include "worker_files.h"
#include "bootstrap_registry.h"
#include <memory>
namespace disked {
namespace {
using namespace worker_files;using V=json::Value;namespace r=report_operation;namespace e=evidence::proposal;
constexpr std::size_t header_limit=r::definition_limit;
const wchar_t* const request_name=L"report.request";
const wchar_t* const records_name=L"report.records";
const wchar_t* const cancel_name=L"report.cancel";
const wchar_t* const lock_name=L"report.admission";
[[noreturn]] void reject(const char* code) {throw Failure(code,0);}
const V& field(const V& v,const char* n) {const auto p=v.find(n);if(!p)reject("report_worker_shape");return *p;}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("report_worker_integer");return std::stoull(v.text);}
std::string encode(const V& v) {return json::dump(v,r::definition_limits());}
void identifier(const std::string& id) {if(id.size()!=42 || id.substr(0,10)!="report-op:" || id.find_first_not_of("0123456789abcdef",10)!=id.npos)reject("report_worker_identity");}
V store_binding(const Directory& dir) {
    dir.check();auto names=V::array();for(const auto n:{request_name,records_name,cancel_name,lock_name})names.items.push_back(V::string(narrow(n)));
    const auto gen=local_file::generation(dir.pinned.back().value,true);
    return V::object().put("path",V::string(narrow(dir.path))).put("generation",gen).put("ancestors",dir.generations)
        .put("access",V::string("create-owned-metadata")).put("children",names).put("failure_domain",V::string("observed-file-volume:"+text(gen,"volume_id")));
}
void no_alias(const V& d,const Directory& dir) {
    const auto& joint=field(d,"export");
    if(encode(field(field(field(joint,"source"),"store"),"generation"))==encode(local_file::generation(dir.pinned.back().value,true)))reject("report_worker_source_store_alias");
    const auto dest=local_file::path_for(text(field(field(field(joint,"effect"),"resources"),"destination"),"location"));
    auto parents=local_file::pin_parents(dest);if(encode(local_file::generation(parents.back().value,true))!=encode(local_file::generation(dir.pinned.back().value,true)))return;
    const auto leaf=dest.substr(dest.find_last_of(L'\\')+1);for(const auto n:{request_name,records_name,cancel_name,lock_name})
        if(CompareStringOrdinal(leaf.c_str(),-1,n,-1,TRUE)==CSTR_EQUAL)reject("report_worker_output_store_alias");
}
void applicable(const V& d,const Directory& dir,const Security& security,const Image& image) {
    r::validate_definition(d);
    if(text(d,"host_id")!=security.host_id || text(d,"image_digest")!=image.digest || text(d,"source_revision")!=bootstrap::source_revision ||
       text(d,"input_digest")!=bootstrap::input_digest || encode(field(d,"store"))!=encode(store_binding(dir)))reject("report_worker_definition_changed");
    no_alias(d,dir);
}
std::unique_ptr<FileAcquisitionExport> reconstruct(const V& d) {
    const auto& joint=field(d,"export");const auto& effect=field(joint,"effect");
    return std::unique_ptr<FileAcquisitionExport>(new FileAcquisitionExport(text(field(joint,"case"),"operation_id"),
        text(field(field(joint,"source"),"store"),"path"),field(field(effect,"artifact"),"policy"),
        text(field(field(effect,"resources"),"destination"),"location"),&joint));
}
V reply(const char* status,const std::string& id,V value,const std::string& diagnostic="",DWORD platform=0) {
    return V::object().put("schema",V::string("org.disked.report-admission-prototype/1")).put("status",V::string(status))
        .put("operation_id",id.empty()?V{}:V::string(id)).put("value",value).put("diagnostic",V::string(diagnostic)).put("platform_code",number(platform));
}
V header_read(const Directory& dir) {
    auto file=dir.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!file.valid())fail("report_worker_request_unavailable");
    const auto raw=read_file(file.value,header_limit);const auto h=json::parse(raw,r::definition_limits());r::validate_header(h);
    if(raw!=encode(h))reject("report_worker_request_noncanonical");return h;
}
V inspect(const std::string& id,const Directory& dir,const V& h) {
    if(text(h,"operation_id")!=id)reject("report_worker_identity");Security security;
    // Compatible historical observation does not require the current executable
    // or the original read/output resources to remain applicable for execution.
    if(text(field(h,"definition"),"host_id")!=security.host_id || encode(field(field(h,"definition"),"store"))!=encode(store_binding(dir)))reject("report_worker_identity");
    auto value=V::object().put("definition",field(h,"definition")).put("definition_digest",field(h,"definition_digest"));
    try {
        auto file=dir.open(records_name,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid() || file_identity(file.value)!=text(h,"records_id"))reject("report_worker_history_identity");
        const auto history=r::read_history(read_file(file.value,r::history_limit),h);
        value.put("state",history.state).put("last_digest",V::string(history.previous)).put("history_complete",V::boolean_value(history.complete));
        const auto& binding=field(history.state,"binding");const auto pid=static_cast<DWORD>(integer(field(binding,"process_id")));
        const auto& resources=field(field(field(field(h,"definition"),"export"),"effect"),"resources");
        const auto producer_path=wide(text(field(resources,"producer"),"location"));
        Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid));std::string observed="unavailable";
        if(process.valid()) {
            if(process_created(process.value)!=text(binding,"process_created"))observed="reused_identity";
            else {
                const auto wait=WaitForSingleObject(process.value,0);
                if(wait==WAIT_OBJECT_0)observed="exited";
                else if(wait==WAIT_TIMEOUT) {
                    wchar_t path[32768];DWORD length=32768;
                    if(!QueryFullProcessImageNameW(process.value,0,path,&length))observed="unavailable";
                    else observed=CompareStringOrdinal(path,static_cast<int>(length),producer_path.c_str(),-1,TRUE)==CSTR_EQUAL?"running":"changed_image_path";
                }
            }
        } else if(GetLastError()==ERROR_INVALID_PARAMETER)observed="exited";
        value.put("worker_observation",V::string(observed));
        if(!history.complete)return reply("unknown",id,value,"report_worker_history_torn");
        if(text(history.state,"phase")!="finished" && observed!="running")return reply("unknown",id,value,"report_worker_unresolved");
        return reply("completed",id,value);
    }catch(const std::exception& error) {return reply("unknown",id,value,error.what());}
}
struct Recorder {
    HANDLE file;const V& header;r::History history;
    void save(V state,const char* point) {
        if(history.count>=r::record_count_limit || file_size(file)>r::history_limit-r::record_limit-1)reject("report_worker_history_limit");
        FILETIME now{};GetSystemTimeAsFileTime(&now);state.put("sequence",number(history.count+1)).put("observed_filetime",number(file_time(now)));
        r::validate_state(state,header,history.count+1);auto row=V::object().put("schema",V::string("org.disked.report-worker-record-prototype/2")).put("state",state).put("previous",V::string(history.previous));
        const auto hash_value=hash(json::dump(row,r::row_limits()));row.put("digest",V::string(hash_value));
        write_file(file,json::dump(row,r::row_limits())+'\n',point);history.state=state;history.previous=hash_value;++history.count;
    }
};
#ifdef DISKED_REPORT_WORKER_TESTING
void delay(const wchar_t* key) {if(GetEnvironmentVariableW(key,nullptr,0))Sleep(5000);}
#else
void delay(const wchar_t*) {}
#endif
}
V prepare_report_worker(const std::string& id,const std::string& case_dir,const V& policy,const std::string& destination,const std::string& execution_dir) {
    Directory dir(execution_dir);dir.empty();Security security;Image image;FileAcquisitionExport session(id,case_dir,policy,destination);
    auto d=V::object().put("schema",V::string("org.disked.report-worker-definition-prototype/1")).put("export",session.definition().value())
        .put("store",store_binding(dir)).put("host_id",V::string(security.host_id)).put("image_digest",V::string(image.digest))
        .put("source_revision",V::string(bootstrap::source_revision)).put("input_digest",V::string(bootstrap::input_digest)).put("target_profile",V::string(bootstrap::target));
    r::validate_definition(d);no_alias(d,dir);return V::object().put("definition",d).put("definition_digest",V::string(r::digest(d)));
}
V start_report_worker(const V& d,const V& g) {
    std::string id;bool claimed=false,existing=false;
    try {
        // Validate all authority before following any supplied resource path.
        r::validate_definition(d);r::validate_grant(g,d);Directory dir(text(field(d,"store"),"path"));Security security;Image image;
        Directory code_parent(narrow(image.path.substr(0,image.path.find_last_of(L'\\'))));applicable(d,dir,security,image);
        if(GetFileAttributesW(dir.child(request_name).c_str())!=INVALID_FILE_ATTRIBUTES) {
            existing=true;const auto h=header_read(dir);id=text(h,"operation_id");
            if(text(h,"definition_digest")!=r::digest(d) || encode(field(h,"grant"))!=encode(g))reject("report_worker_existing_definition_conflict");
            auto observed=inspect(id,dir,h);if(text(observed,"status")=="completed" && text(field(field(observed,"value"),"state"),"phase")!="finished")observed.put("status",V::string("accepted_running"));return observed;
        }
        dir.empty();{auto reviewed=reconstruct(d);}
        ULARGE_INTEGER free{};if(!GetDiskFreeSpaceExW(dir.path.c_str(),&free,nullptr,nullptr))fail("report_worker_capacity_observation");
        if(free.QuadPart<r::history_limit+header_limit)reject("report_worker_capacity");auto attributes=security.attributes;id=security.identity("report-op:");
        auto lock=dir.open(lock_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes,&claimed);if(!lock.valid())fail("report_worker_busy");
        auto records=dir.open(records_name,GENERIC_READ|FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);if(!records.valid())fail("report_worker_store_create");
        auto cancel=dir.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);if(!cancel.valid())fail("report_worker_store_create");write_file(cancel.value,"0","report_cancel_create");
        auto h=V::object().put("schema",V::string("org.disked.report-worker-request-prototype/1")).put("operation_id",V::string(id)).put("worker_epoch",V::string(security.identity("worker:")))
            .put("attempt_id",V::string(security.identity("attempt:"))).put("definition",d).put("definition_digest",V::string(r::digest(d))).put("grant",g)
            .put("records_id",V::string(file_identity(records.value))).put("cancel_id",V::string(file_identity(cancel.value)));r::validate_header(h);
        auto output=dir.open(request_name,GENERIC_WRITE,0,CREATE_NEW,&attributes);if(!output.valid())fail("report_worker_store_create");write_file(output.value,encode(h),"report_request");output=Handle();
        auto input=dir.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!input.valid() || read_file(input.value,header_limit)!=encode(h))reject("report_worker_request_changed");
        Handle event(CreateEventW(&attributes,TRUE,FALSE,nullptr));if(!event.valid())fail("report_worker_event_create");
        auto ci=inherited(input.value,GENERIC_READ),cr=inherited(records.value,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES),cc=inherited(cancel.value,GENERIC_READ),ce=inherited(event.value,EVENT_MODIFY_STATE|SYNCHRONIZE);
        std::vector<HANDLE> handles={ci.value,cr.value,cc.value,ce.value};WorkerBudget aggregate(security,true);Handle job(CreateJobObjectW(&attributes,nullptr));if(!job.valid())fail("report_worker_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
        if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("report_worker_job_limits");std::vector<HANDLE> jobs={aggregate.job.value,job.value};AttributeList list(handles,jobs);
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=list.list;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
        std::wstring command=L"\""+image.path+L"\" __disked_report_worker";for(const auto handle:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(handle));
        dir.check();code_parent.check();PROCESS_INFORMATION raw{};
        if(!CreateProcessW(image.path.c_str(),&command[0],nullptr,nullptr,TRUE,DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,dir.path.c_str(),&startup.StartupInfo,&raw))fail("report_worker_spawn_failed");
        Handle process(raw.hProcess),thread(raw.hThread);ci=Handle();cr=Handle();cc=Handle();ce=Handle();input=Handle();records=Handle();cancel=Handle();
        HANDLE waits[]={event.value,process.value};const auto wait=WaitForMultipleObjects(2,waits,FALSE,3000);
        if(wait!=WAIT_OBJECT_0)return reply("unknown",id,V::object().put("admission",V::string("unresolved")),"report_worker_admission_unresolved");
        auto observed=inspect(id,dir,h);if(text(observed,"status")=="completed" && text(field(field(observed,"value"),"state"),"phase")!="finished")observed.put("status",V::string("accepted_running"));return observed;
    }catch(const Failure& error) {return reply(claimed||existing?"unknown":"refused",claimed||existing?id:"",V::object(),error.what(),error.platform);}
     catch(const FileReportExportError& error) {return reply(claimed||existing?"unknown":"refused",claimed||existing?id:"",V::object(),error.what(),error.platform_code);}
     catch(const std::exception& error) {return reply(claimed||existing?"unknown":"refused",claimed||existing?id:"",V::object(),error.what());}
}
V observe_report_worker(const std::string& id,const std::string& directory,bool cancel_request) {
    try {
        identifier(id);Directory dir(directory);const auto h=header_read(dir);auto observed=inspect(id,dir,h);
        if(cancel_request && text(observed,"status")=="completed") {
            auto& value=observed.fields["value"];if(text(field(value,"state"),"phase")=="finished")value.put("cancellation_request",V::string("too_late"));
            else {
                auto file=dir.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);if(!file.valid() || file_identity(file.value)!=text(h,"cancel_id"))reject("report_worker_cancel_identity");
                const auto flag=read_file(file.value,1);if(flag!="0" && flag!="1")reject("report_worker_cancel_invalid");LARGE_INTEGER zero{};if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))fail("report_worker_cancel_seek");
                write_file(file.value,"1","report_cancel_request");value.put("cancellation_request",V::string("requested"));
            }
        }
        return observed;
    }catch(const Failure& error) {return reply("unknown",id,V::object(),error.what(),error.platform);}
     catch(const std::exception& error) {return reply("unknown",id,V::object(),error.what());}
}
int run_report_worker(int argc,wchar_t** argv) {
    try {
        if(argc!=6)reject("report_worker_role_arguments");std::vector<HANDLE> capabilities;for(int i=2;i<6;++i)capabilities.push_back(argument_handle(argv[i]));
        for(std::size_t i=0;i<capabilities.size();++i)for(std::size_t j=0;j<i;++j)if(capabilities[i]==capabilities[j])reject("report_worker_role_capability");
        Handle input(capabilities[0]),records(capabilities[1]),cancel(capabilities[2]),event(capabilities[3]);for(const auto h:capabilities)if(!SetHandleInformation(h,HANDLE_FLAG_INHERIT,0))reject("report_worker_role_capability");
        for(const auto channel:{STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE}) {DWORD flags=0;const auto h=GetStdHandle(channel);if(h && h!=INVALID_HANDLE_VALUE && GetHandleInformation(h,&flags))reject("report_worker_role_standard_handle");}
        if(file_size(records.value)!=0 || file_size(cancel.value)!=1 || WaitForSingleObject(event.value,0)!=WAIT_TIMEOUT)reject("report_worker_role_capability");
        const auto path=final_path(input.value),rp=final_path(records.value),cp=final_path(cancel.value);const auto slash=path.find_last_of(L'\\');const auto parent=path.substr(0,slash+1);
        if(path.compare(0,4,L"\\\\?\\") || path.substr(slash+1)!=request_name || rp!=parent+records_name || cp!=parent+cancel_name)reject("report_worker_role_capability");
        Directory dir(narrow(parent.substr(4,parent.size()-5)));const auto h=json::parse(read_file(input.value,header_limit),r::definition_limits());const auto persisted=header_read(dir);
        if(encode(h)!=encode(persisted) || text(h,"records_id")!=file_identity(records.value) || text(h,"cancel_id")!=file_identity(cancel.value))reject("report_worker_role_capability");
        Security security;Image image;applicable(field(h,"definition"),dir,security,image);WorkerBudget aggregate(security,false);JOBOBJECT_EXTENDED_LIMIT_INFORMATION budget{};
        if(!QueryInformationJobObject(nullptr,JobObjectExtendedLimitInformation,&budget,sizeof(budget),nullptr) || budget.BasicLimitInformation.ActiveProcessLimit!=1 || budget.ProcessMemoryLimit!=128*1024*1024 ||
           budget.BasicLimitInformation.LimitFlags!=(JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY))reject("report_worker_role_budget");
        auto binding=r::expected_binding(h);binding.put("process_id",number(GetCurrentProcessId())).put("process_created",V::string(process_created(GetCurrentProcess())));
        auto state=V::object().put("schema",V::string("org.disked.report-worker-state-prototype/2")).put("binding",binding).put("sequence",number(0)).put("phase",V::string("prepared"))
            .put("cancellation_observation",V::string("not_observed")).put("effect_certainty",V::string("not_started")).put("observed_filetime",number(0)).put("quiescent",V::boolean_value(false)).put("outcome",V{}).put("receipt",V{});
        Recorder recorder{records.value,h,r::History{}};recorder.save(state,"report_prepared");FileAcquisitionExportResult result;std::unique_ptr<FileAcquisitionExport> session;bool dispatched=false;
        try {
            session=reconstruct(field(h,"definition"));delay(L"DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY");
            if(!SetEvent(event.value))fail("report_worker_admission_signal");event=Handle();delay(L"DISKED_REPORT_WORKER_TEST_EFFECT_DELAY");
            state.put("phase",V::string("executing")).put("effect_certainty",V::string("in_flight"));recorder.save(state,"report_executing");dispatched=true;
            const auto stop=[&] {
                const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")reject("report_worker_cancel_invalid");
                if(flag=="1" && text(state,"cancellation_observation")=="not_observed") {state.put("cancellation_observation",V::string("observed"));recorder.save(state,"report_cancel_observed");}
                return flag=="1";
            };
            const auto& joint=field(field(h,"definition"),"export");result=session->execute(e::AcquisitionExportGrant{r::digest(joint),true,true,true},stop);
        }catch(const std::exception& error) {
            result.outcome.diagnostic=error.what();result.outcome.output.diagnostic=error.what();
            if(dispatched) {result.outcome.status="unknown";result.outcome.output.status="failed";result.outcome.output.output_state="uncertain";result.outcome.output.uncertain_effect=true;result.outcome.output.written_known=false;}
        }
        session.reset(); // Handles are released before recording effect quiescence.
        delay(L"DISKED_REPORT_WORKER_TEST_RECEIPT_DELAY");state.put("phase",V::string("finished")).put("quiescent",V::boolean_value(true))
            .put("effect_certainty",V::string(result.outcome.output.uncertain_effect?"uncertain":"observed")).put("outcome",result.outcome.view()).put("receipt",result.receipt);
        recorder.save(state,"report_finished");if(event.valid())SetEvent(event.value);return 0;
    }catch(...) {return 199;}
}
}
