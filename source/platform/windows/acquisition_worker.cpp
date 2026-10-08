#include "acquisition_worker.h"
#include "operation.h"
#include "observation.h"
#include "commands.h"
#include "worker_files.h"
#include "local_file.h"
#include "bootstrap_registry.h"
#include <algorithm>
#include <memory>

namespace disked {
namespace {
using namespace worker_files;
using V=json::Value;
[[noreturn]] void reject(const char* code) {throw Failure(code,0);}
constexpr std::size_t record_limit=16384,history_limit=1048576,record_count_limit=64;
const wchar_t* const request_name=L"acquisition.request";
const wchar_t* const records_name=L"acquisition.records";
const wchar_t* const cancel_name=L"acquisition.cancel";
const wchar_t* const lock_name=L"acquisition.admission";
V number(std::uint64_t n) {return V::string(std::to_string(n));}
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)reject("acquisition_worker_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())reject("acquisition_worker_shape");for(const auto n:names)field(v,n);
}
void identifier(const std::string& v,const char* prefix,std::size_t length) {
    const std::string p=prefix;if(v.size()!=p.size()+length || v.compare(0,p.size(),p) || v.find_first_not_of("0123456789abcdef",p.size())!=std::string::npos)reject("acquisition_worker_identity");
}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("acquisition_worker_integer");return std::stoull(v.text);}
bool boolean(const V& v) {if(v.kind!=V::Kind::boolean)reject("acquisition_worker_shape");return v.boolean;}
std::string digest(const V& v) {return "sha256:"+hash(json::dump(v));}
std::uint64_t now() {FILETIME t{};GetSystemTimeAsFileTime(&t);return file_time(t);}
json::Limits row_limits() {json::Limits l;l.bytes=record_limit;l.depth=20;l.values=2048;l.string_bytes=1024;return l;}
V request_value(const FileAcquisitionRequest& r) {
    return V::object().put("source",V::string(r.source)).put("destination",V::string(r.destination)).put("map",V::string(r.map))
        .put("resume",V::boolean_value(r.resume)).put("explicit_options",V::boolean_value(r.explicit_options)).put("chunk_bytes",number(r.chunk_bytes))
        .put("retry_limit",number(r.retries)).put("read_policy",V::string(r.read_policy)).put("substitution",V::string(r.substitution));
}
FileAcquisitionRequest request_from(const V& v) {
    keys(v,{"source","destination","map","resume","explicit_options","chunk_bytes","retry_limit","read_policy","substitution"});
    FileAcquisitionRequest r;r.source=text(v,"source");r.destination=text(v,"destination");r.map=text(v,"map");
    r.resume=boolean(field(v,"resume"));r.explicit_options=boolean(field(v,"explicit_options"));
    const auto n=integer(field(v,"chunk_bytes")),retry=integer(field(v,"retry_limit"));if(n>0xffffffffULL || retry>0xffffffffULL)reject("acquisition_worker_integer");
    r.chunk_bytes=static_cast<std::uint32_t>(n);r.retries=static_cast<std::uint32_t>(retry);r.read_policy=text(v,"read_policy");r.substitution=text(v,"substitution");return r;
}
V store_binding(const Directory& directory) {
    auto names=V::array();for(const auto n:{request_name,records_name,cancel_name,lock_name})names.items.push_back(V::string(narrow(n)));
    return V::object().put("path",V::string(narrow(directory.path))).put("generation",local_file::generation(directory.pinned.back().value,true))
        .put("access",V::string("create-owned-metadata")).put("children",names).put("failure_domain",V::string("observed-file-volume:"+text(local_file::generation(directory.pinned.back().value,true),"volume_id")));
}
void no_store_alias(const Directory& directory,const FileAcquisitionRequest& r) {
    const auto generation=local_file::generation(directory.pinned.back().value,true);
    for(const auto& path:{r.source,r.destination,r.map}) {
        const auto p=local_file::path_for(path);auto parents=local_file::pin_parents(p);
        if(json::dump(local_file::generation(parents.back().value,true))!=json::dump(generation))continue;
        const auto leaf=p.substr(p.find_last_of(L'\\')+1);
        for(const auto name:{request_name,records_name,cancel_name,lock_name})if(CompareStringOrdinal(leaf.c_str(),-1,name,-1,TRUE)==CSTR_EQUAL)reject("acquisition_operation_store_alias");
    }
}
void definition_valid(const V& d) {
    keys(d,{"schema","request","plan","store","host_id","image_digest","source_revision","input_digest","target_profile"});
    if(text(d,"schema")!="org.disked.acquisition-worker-definition/1" || text(d,"target_profile")!="windows.nt10.x64.win32")reject("acquisition_worker_version");
    if(!request_from(field(d,"request")).explicit_options)reject("acquisition_definition_options");
    acquisition::prepare(field(d,"plan"));
    keys(field(d,"store"),{"path","generation","access","children","failure_domain"});
    identifier(text(d,"host_id"),"",64);identifier(text(d,"image_digest"),"",64);identifier(text(d,"source_revision"),"",40);identifier(text(d,"input_digest"),"sha256:",64);
    json::dump(d,row_limits());
}
acquisition::Grant grant_valid(const V& grant,const V& definition) {
    keys(grant,{"definition_digest","source_read","destination_write","map_write","host_effects"});
    if(text(grant,"definition_digest")!=digest(definition))reject("acquisition_worker_grant");
    acquisition::Grant g{acquisition::prepare(field(definition,"plan")).digest,
        boolean(field(grant,"source_read")),boolean(field(grant,"destination_write")),boolean(field(grant,"map_write")),boolean(field(grant,"host_effects"))};
    if(!g.source_read || !g.destination_write || !g.map_write || !g.host_effects)reject("acquisition_worker_grant");return g;
}
void applicable(const V& d,const Directory& directory,const Security& security,const Image& image) {
    definition_valid(d);
    if(text(d,"host_id")!=security.host_id || text(d,"image_digest")!=image.digest || text(d,"source_revision")!=bootstrap::source_revision ||
        text(d,"input_digest")!=bootstrap::input_digest || json::dump(field(d,"store"))!=json::dump(store_binding(directory)))reject("acquisition_definition_changed");
    no_store_alias(directory,request_from(field(d,"request")));
}
V reply(const char* status,const std::string& id,V value,const std::string& diagnostic="",DWORD platform=0) {
    return V::object().put("schema",V::string("org.disked.acquisition-admission-prototype/1")).put("status",V::string(status))
        .put("operation_id",id.empty()?V{}:V::string(id)).put("value",value).put("diagnostic",V::string(diagnostic)).put("platform_code",number(platform));
}
V header_read(const Directory& directory) {
    auto input=directory.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!input.valid())worker_files::fail("acquisition_request_unavailable");
    const auto v=json::parse(read_file(input.value,32768));
    keys(v,{"schema","operation_id","worker_epoch","attempt_id","definition","definition_digest","grant","records_id","cancel_id"});
    if(text(v,"schema")!="org.disked.acquisition-worker-request/1" || text(v,"definition_digest")!=digest(field(v,"definition")))reject("acquisition_request_invalid");
    identifier(text(v,"operation_id"),"image-op:",32);identifier(text(v,"worker_epoch"),"worker:",32);identifier(text(v,"attempt_id"),"attempt:",32);
    definition_valid(field(v,"definition"));grant_valid(field(v,"grant"),field(v,"definition"));return v;
}
using History=acquisition_operation::History;
using acquisition_operation::expected_binding;
void state_valid(const V& state,const V& header,std::size_t sequence) {acquisition_operation::validate_state(state,header,sequence);}
History history_read(HANDLE file,const V& header) {return acquisition_operation::read_history(read_file(file,history_limit),header);}
V inspect(const std::string& id,const Directory& directory,const V& header,History* history=nullptr) {
    if(text(header,"operation_id")!=id)reject("acquisition_worker_identity");Security security;
    if(text(field(header,"definition"),"host_id")!=security.host_id || json::dump(field(field(header,"definition"),"store"))!=json::dump(store_binding(directory)))reject("acquisition_worker_identity");
    auto value=V::object().put("definition",field(header,"definition")).put("definition_digest",field(header,"definition_digest"));
    try {
        auto file=directory.open(records_name,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid() || file_identity(file.value)!=text(header,"records_id"))reject("acquisition_worker_history_identity");
        const auto h=history_read(file.value,header);if(history)*history=h;
        value.put("state",h.state).put("last_digest",V::string(h.previous));
        const auto& b=field(h.state,"binding");const auto pid=static_cast<DWORD>(integer(field(b,"process_id")));
        Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid));std::string observed="unavailable";
        if(process.valid())observed=process_created(process.value)!=text(b,"process_created")?"reused_identity":WaitForSingleObject(process.value,0)==WAIT_TIMEOUT?"running":"exited";
        else if(GetLastError()==ERROR_INVALID_PARAMETER)observed="exited";
        value.put("worker_observation",V::string(observed));
        if(!h.complete)return reply("unknown",id,value,"acquisition_worker_history_torn");
        if(text(h.state,"phase")!="finished" && observed!="running")return reply("unknown",id,value,"acquisition_worker_unresolved");
        return reply("completed",id,value);
    } catch(const std::exception& e) {return reply("unknown",id,value,e.what());}
}
struct Recorder {
    HANDLE file;const V& header;History history;
    void save(V state) {
        if(history.count>=record_count_limit || file_size(file)>history_limit-record_limit-1)reject("acquisition_worker_history_limit");
        state.put("sequence",number(history.count+1));state.put("observed_filetime",number(now()));state_valid(state,header,history.count+1);
        auto row=V::object().put("schema",V::string("org.disked.acquisition-worker-record/1")).put("state",state).put("previous",V::string(history.previous));
        const auto hash_value=hash(json::dump(row,row_limits()));row.put("digest",V::string(hash_value));
        write_file(file,json::dump(row,row_limits())+'\n',"acquisition_record");history.state=state;history.previous=hash_value;++history.count;
    }
};
}
V prepare_acquisition_worker(const FileAcquisitionRequest& request,const std::string& state_directory) {
    Directory directory(state_directory);directory.empty();Security security;Image image;no_store_alias(directory,request);FileAcquisition session(request);
    auto definition=V::object().put("schema",V::string("org.disked.acquisition-worker-definition/1")).put("request",request_value(request)).put("plan",session.plan().definition)
        .put("store",store_binding(directory)).put("host_id",V::string(security.host_id)).put("image_digest",V::string(image.digest))
        .put("source_revision",V::string(bootstrap::source_revision)).put("input_digest",V::string(bootstrap::input_digest)).put("target_profile",V::string(bootstrap::target));
    auto resolved=request;resolved.explicit_options=true;resolved.chunk_bytes=session.plan().chunk_bytes;resolved.retries=session.plan().retries;
    resolved.read_policy=text(session.plan().definition,"read_policy");resolved.substitution=text(session.plan().definition,"substitution");definition.put("request",request_value(resolved));
    definition_valid(definition);return V::object().put("definition",definition).put("definition_digest",V::string(digest(definition)));
}
V start_acquisition_worker(const V& definition,const V& grant) {
    std::string id;
    try {
        definition_valid(definition);grant_valid(grant,definition);
        Directory directory(text(field(definition,"store"),"path"));Security security;Image image;
        // The state directory need not share ancestors with the executable.
        // Pin its code parents separately through launch, so changing an
        // executable directory cannot redirect CreateProcess's reviewed path.
        Directory code_parent(narrow(image.path.substr(0,image.path.find_last_of(L'\\'))));
        applicable(definition,directory,security,image);
        if(GetFileAttributesW(directory.child(request_name).c_str())!=INVALID_FILE_ATTRIBUTES) {
            const auto header=header_read(directory);id=text(header,"operation_id");
            if(text(header,"definition_digest")!=digest(definition) || json::dump(field(header,"grant"))!=json::dump(grant))reject("acquisition_existing_definition_conflict");
            auto observed=inspect(id,directory,header);
            if(text(observed,"status")=="completed" && text(field(field(observed,"value"),"state"),"phase")=="active")observed.put("status",V::string("accepted_running"));
            return observed;
        }
        directory.empty();const auto request=request_from(field(definition,"request"));
        // A resume's read-only preparation handles must not prevent the worker
        // reopening outputs exclusively. The child revalidates this exact plan
        // under its own pinned source/output/code handles before any data effect.
        {FileAcquisition reviewed(request,&field(definition,"plan"));}
        ULARGE_INTEGER available{};if(!GetDiskFreeSpaceExW(directory.path.c_str(),&available,nullptr,nullptr))worker_files::fail("acquisition_operation_capacity_observation");
        if(available.QuadPart<history_limit+32768)reject("acquisition_operation_capacity");
        auto attributes=security.attributes;
        auto lock=directory.open(lock_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes);if(!lock.valid())worker_files::fail("acquisition_operation_busy");
        id=security.identity("image-op:");
        auto records=directory.open(records_name,GENERIC_READ|FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);
        if(!records.valid())worker_files::fail("acquisition_operation_create");
        auto cancel=directory.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);
        if(!cancel.valid())worker_files::fail("acquisition_operation_create");write_file(cancel.value,"0","acquisition_cancel_create");
        auto header=V::object().put("schema",V::string("org.disked.acquisition-worker-request/1")).put("operation_id",V::string(id))
            .put("worker_epoch",V::string(security.identity("worker:"))).put("attempt_id",V::string(security.identity("attempt:")))
            .put("definition",definition).put("definition_digest",V::string(digest(definition))).put("grant",grant)
            .put("records_id",V::string(file_identity(records.value))).put("cancel_id",V::string(file_identity(cancel.value)));
        auto output=directory.open(request_name,GENERIC_WRITE,0,CREATE_NEW,&attributes);if(!output.valid())worker_files::fail("acquisition_operation_create");
        write_file(output.value,json::dump(header),"acquisition_request");output=Handle();
        auto input=directory.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!input.valid() || read_file(input.value,32768)!=json::dump(header))reject("acquisition_request_changed");
        Handle event(CreateEventW(&attributes,TRUE,FALSE,nullptr));if(!event.valid())worker_files::fail("acquisition_event_create");
        auto child_input=inherited(input.value,GENERIC_READ),child_records=inherited(records.value,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES),child_cancel=inherited(cancel.value,GENERIC_READ),child_event=inherited(event.value,EVENT_MODIFY_STATE|SYNCHRONIZE);
        std::vector<HANDLE> handles={child_input.value,child_records.value,child_cancel.value,child_event.value};
        WorkerBudget aggregate(security,true);Handle job(CreateJobObjectW(&attributes,nullptr));if(!job.valid())worker_files::fail("acquisition_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;
        limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
        if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))worker_files::fail("acquisition_job_limits");
        std::vector<HANDLE> jobs={aggregate.job.value,job.value};AttributeList list(handles,jobs);
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=list.list;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
        std::wstring command=L"\""+image.path+L"\" __disked_acquisition_worker";for(const auto h:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(h));
        PROCESS_INFORMATION raw{};if(!CreateProcessW(image.path.c_str(),&command[0],nullptr,nullptr,TRUE,DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,directory.path.c_str(),&startup.StartupInfo,&raw))worker_files::fail("acquisition_spawn_failed");
        Handle process(raw.hProcess),thread(raw.hThread);child_input=Handle();child_records=Handle();child_cancel=Handle();child_event=Handle();input=Handle();records=Handle();cancel=Handle();
        HANDLE waits[]={event.value,process.value};const auto wait=WaitForMultipleObjects(2,waits,FALSE,3000);
        if(wait!=WAIT_OBJECT_0)return reply("unknown",id,V::object().put("admission",V::string("unresolved")),"acquisition_admission_unresolved");
        auto observed=inspect(id,directory,header);
        if(text(observed,"status")=="completed" && text(field(field(observed,"value"),"state"),"phase")=="active")observed.put("status",V::string("accepted_running"));
        return observed;
    } catch(const Failure& e) {return reply(id.empty()?"refused":"unknown",id,V::object(),e.what(),e.platform);}
      catch(const FileAcquisitionError& e) {return reply(id.empty()?"refused":"unknown",id,V::object(),e.what(),e.platform_code);}
      catch(const std::exception& e) {return reply(id.empty()?"refused":"unknown",id,V::object(),e.what());}
}
V observe_acquisition_worker(const std::string& id,const std::string& state_directory,bool cancel_request) {
    try {
        identifier(id,"image-op:",32);Directory directory(state_directory);const auto header=header_read(directory);auto observed=inspect(id,directory,header);
        if(cancel_request && text(observed,"status")=="completed") {
            auto& value=observed.fields["value"];
            if(text(field(value,"state"),"phase")=="finished")value.put("cancellation_request",V::string("too_late"));
            else {
                auto cancel=directory.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
                if(!cancel.valid() || file_identity(cancel.value)!=text(header,"cancel_id"))reject("acquisition_cancel_identity");
                const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")reject("acquisition_cancel_invalid");
                LARGE_INTEGER zero{};if(!SetFilePointerEx(cancel.value,zero,nullptr,FILE_BEGIN))worker_files::fail("acquisition_cancel_seek");
                write_file(cancel.value,"1","acquisition_cancel_request");value.put("cancellation_request",V::string("requested"));
            }
        }
        return observed;
    } catch(const Failure& e) {return reply("unknown",id,V::object(),e.what(),e.platform);}
      catch(const std::exception& e) {return reply("unknown",id,V::object(),e.what());}
}
Outcome watch_acquisition_worker(const std::string& request,const V& parameters,const std::shared_ptr<WatchQueue>& events) {
    const auto invalid=validate_watch_parameters(parameters);if(!invalid.empty())return refused(request,invalid);
    std::string id;V last=V::object();
    try {
        id=text(parameters,"operation_id");identifier(id,"image-op:",32);
        Directory directory(text(parameters,"state_directory"));const auto header=header_read(directory);Security security;
        if(text(header,"operation_id")!=id)reject("acquisition_worker_identity");
        const auto observer=security.identity("watch:");
        WatchCursor cursor(id,request,observer,parameters,acquisition_watch_profile(field(header,"definition")));
        auto collected=V::array();V last_state;std::size_t bytes=0;
        const auto* follow=parameters.find("follow_ms");const auto end=GetTickCount64()+(follow?std::stoull(follow->text):0);
        for(;;) {
            History history;auto observed=inspect(id,directory,header,&history);
            if(history.count) {
                std::vector<V> batch;
                try {batch=cursor.project(history.state,history.records,history.previous);}
                catch(const std::invalid_argument& error) {return refused(request,error.what());}
                for(const auto& item:batch) {
                    json::Limits limits;limits.bytes=32768;const auto size=json::dump(item,limits).size();
                    if(collected.items.size()>=64 || size>1048576-bytes)throw std::invalid_argument("watch_queue_limit");
                    collected.items.push_back(item);bytes+=size;
                    if(events && !events->push(item))return acquisition_observation(request,observed);
                }
                last_state=history.state;
            }
            auto out=acquisition_observation(request,observed);auto& value=out.response.fields["result"];
            value.put("events",events?V::array():collected).put("observer_epoch",V::string(observer))
                .put("last_sequence",V::string(cursor.sequence())).put("last_digest",V::string(cursor.digest()))
                .put("worker_epoch",cursor.worker().empty()?V{}:V::string(cursor.worker()));
            if(!history.count && last_state.kind!=V::Kind::null)value.put("last_validated_state",last_state);
            last=value;
            if(out.exit_code || (history.count && text(history.state,"phase")=="finished"))return out;
            if(GetTickCount64()>=end) {out.response.put("status",V::string("accepted_running"));out.exit_code=5;return out;}
            Sleep(25);
        }
    } catch(const Failure& error) {return acquisition_observation(request,reply("unknown",id,last,error.what(),error.platform));}
      catch(const std::exception& error) {return acquisition_observation(request,reply("unknown",id,last,error.what()));}
}
Outcome dispatch_acquisition_operation(const std::string& request,const std::string& command,const V& parameters) {
    if(command=="operation.watch")return watch_acquisition_worker(request,parameters);
    if(command!="operation.inspect" && command!="operation.cancel.request")return refused(request,"command_unavailable",3);
    return acquisition_observation(request,observe_acquisition_worker(text(parameters,"operation_id"),text(parameters,"state_directory"),command=="operation.cancel.request"));
}
int run_acquisition_worker(int argc,wchar_t** argv) {
    try {
        if(argc!=6)reject("acquisition_role_arguments");std::vector<HANDLE> capabilities;
        for(int i=2;i<6;++i)capabilities.push_back(argument_handle(argv[i]));
        for(std::size_t i=0;i<capabilities.size();++i)for(std::size_t j=0;j<i;++j)if(capabilities[i]==capabilities[j])reject("acquisition_role_capability");
        Handle input(capabilities[0]),records(capabilities[1]),cancel(capabilities[2]),event(capabilities[3]);
        for(const auto h:capabilities)if(!SetHandleInformation(h,HANDLE_FLAG_INHERIT,0))reject("acquisition_role_capability");
        for(const auto channel:{STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE}) {DWORD flags=0;const auto h=GetStdHandle(channel);if(h && h!=INVALID_HANDLE_VALUE && GetHandleInformation(h,&flags))reject("acquisition_role_standard_handle");}
        if(file_size(records.value)!=0 || file_size(cancel.value)!=1 || WaitForSingleObject(event.value,0)!=WAIT_TIMEOUT)reject("acquisition_role_capability");
        const auto input_path=final_path(input.value),record_path=final_path(records.value),cancel_path=final_path(cancel.value);
        const auto slash=input_path.find_last_of(L'\\');const auto parent=input_path.substr(0,slash+1);
        if(input_path.compare(0,4,L"\\\\?\\") || input_path.substr(slash+1)!=request_name || record_path!=parent+records_name || cancel_path!=parent+cancel_name)reject("acquisition_role_capability");
        const auto header=json::parse(read_file(input.value,32768));Directory directory(narrow(parent.substr(4,parent.size()-5)));
        const auto persisted=header_read(directory);if(json::dump(header)!=json::dump(persisted) || text(header,"records_id")!=file_identity(records.value) || text(header,"cancel_id")!=file_identity(cancel.value))reject("acquisition_role_capability");
        Security security;Image image;applicable(field(header,"definition"),directory,security,image);WorkerBudget aggregate(security,false);
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION budget{};
        if(!QueryInformationJobObject(nullptr,JobObjectExtendedLimitInformation,&budget,sizeof(budget),nullptr) || budget.BasicLimitInformation.ActiveProcessLimit!=1 || budget.ProcessMemoryLimit!=128*1024*1024 ||
           (budget.BasicLimitInformation.LimitFlags&(JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY))!=(JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY) ||
           (budget.BasicLimitInformation.LimitFlags&JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE))reject("acquisition_role_budget");
        auto binding=expected_binding(header);binding.put("process_id",number(GetCurrentProcessId())).put("process_created",V::string(process_created(GetCurrentProcess())));
        auto state=V::object().put("schema",V::string("org.disked.acquisition-worker-state/1")).put("binding",binding).put("sequence",number(0)).put("phase",V::string("active"))
            .put("checkpoint_bytes",number(0)).put("source_bytes",number(0)).put("substituted_bytes",number(0)).put("observed_filetime",number(0)).put("quiescent",V::boolean_value(false)).put("outcome",V{}).put("receipt",V{});
        Recorder recorder{records.value,header,History{}};recorder.save(state);
        FileAcquisitionResult result;std::unique_ptr<FileAcquisition> session;
        try {
            const auto& definition=field(header,"definition");const auto request=request_from(field(definition,"request"));const auto grant=grant_valid(field(header,"grant"),definition);
            session.reset(new FileAcquisition(request,&field(definition,"plan")));
#ifdef DISKED_ACQUISITION_WORKER_TESTING
            if(GetEnvironmentVariableW(L"DISKED_ACQ_WORKER_TEST_ADMISSION_DELAY",nullptr,0))Sleep(5000);
#endif
            if(!SetEvent(event.value))worker_files::fail("acquisition_admission_signal");event=Handle();
            FileAcquisitionHooks hooks;hooks.attempt_id=text(header,"attempt_id");
            hooks.stop=[&]() {const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")reject("acquisition_cancel_invalid");return flag=="1";};
            const auto total=session->plan().bytes;const auto quantum=std::max<std::uint64_t>(1,total/32+(total%32?1:0));std::uint64_t next=quantum;
            hooks.checkpoint=[&](const acquisition::Outcome& out) {
#ifdef DISKED_ACQUISITION_WORKER_TESTING
                if(GetEnvironmentVariableW(L"DISKED_ACQ_WORKER_TEST_CHECKPOINT_DELAY",nullptr,0))Sleep(150);
                if(GetEnvironmentVariableW(L"DISKED_ACQ_WORKER_TEST_CHECKPOINT_OBSERVER_ERROR",nullptr,0))reject("acquisition_test_observer_error");
#endif
                if(out.checkpoint_bytes<next)return;
                state.put("checkpoint_bytes",number(out.checkpoint_bytes)).put("source_bytes",number(out.source_bytes)).put("substituted_bytes",number(out.substituted_bytes));
                recorder.save(state);next=(out.checkpoint_bytes/quantum+1)*quantum;
            };
            result=session->execute(grant,hooks);
        } catch(const std::exception& e) {
            result.outcome.status="failed";result.outcome.diagnostic=e.what();result.outcome.uncertain_effect=true;
            result.outcome.checkpoint_bytes=integer(field(state,"checkpoint_bytes"));result.outcome.source_bytes=integer(field(state,"source_bytes"));result.outcome.substituted_bytes=integer(field(state,"substituted_bytes"));
        }
        session.reset(); // A terminal receipt never precedes provider-handle release.
        state.put("phase",V::string("finished")).put("quiescent",V::boolean_value(true)).put("checkpoint_bytes",number(result.outcome.checkpoint_bytes))
            .put("source_bytes",number(result.outcome.source_bytes)).put("substituted_bytes",number(result.outcome.substituted_bytes)).put("outcome",result.outcome.report()).put("receipt",result.receipt);
        recorder.save(state);if(event.valid())SetEvent(event.value);return 0;
    } catch(...) {return 199;}
}
}
