#include "verification_worker.h"
#include "file_case.h"
#include "file_verification.h"
#include "report_export.h"
#include "verification_observation.h"
#include "worker_files.h"
#include "bootstrap_registry.h"
#include <memory>
#include <set>
namespace disked {
namespace {
using namespace worker_files;using V=json::Value;namespace r=verification_operation;namespace e=evidence::proposal;
const wchar_t* const request_name=L"verification.request";
const wchar_t* const records_name=L"verification.records";
const wchar_t* const cancel_name=L"verification.cancel";
const wchar_t* const lock_name=L"verification.admission";
const wchar_t* const collection_name=L"verification.collection";
[[noreturn]] void reject(const char* code) {throw Failure(code,0);}
const V& field(const V& v,const char* n) {const auto p=v.find(n);if(!p)reject("verification_worker_shape");return *p;}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("verification_worker_integer");return std::stoull(v.text);}
std::string encode(const V& v) {return json::dump(v,r::definition_limits());}
void identifier(const std::string& id) {if(id.size()!=42 || id.substr(0,10)!="verify-op:" || id.find_first_not_of("0123456789abcdef",10)!=id.npos)reject("verification_worker_identity");}
V code(const Image& image) {
    return V::object().put("source_revision",V::string(bootstrap::source_revision)).put("input_digest",V::string(bootstrap::input_digest))
        .put("configuration_digest",V::string(bootstrap::configuration_digest)).put("image_digest",V::string("sha256:"+image.digest))
        .put("target_profile",V::string(bootstrap::target)).put("source_state",V::string(bootstrap::source_state));
}
V store_binding(const Directory& dir) {
    dir.check();auto names=V::array();for(const auto n:{request_name,records_name,cancel_name,lock_name,collection_name})names.items.push_back(V::string(narrow(n)));
    const auto gen=local_file::generation(dir.pinned.back().value,true);
    return V::object().put("path",V::string(narrow(dir.path))).put("generation",gen).put("ancestors",dir.generations)
        .put("access",V::string("create-owned-private-metadata")).put("children",names).put("failure_domain",V::string("observed-file-volume:"+text(gen,"volume_id")));
}
void applicable(const V& d,const Directory& dir,const Security& security,const Image& image) {
    r::validate_definition(d);
    if(text(d,"host_id")!=security.host_id || text(d,"worker_image_path")!=narrow(image.path) || encode(field(d,"verifier"))!=encode(code(image)) ||
       encode(field(d,"store"))!=encode(store_binding(dir)))reject("verification_worker_definition_changed");
}
struct Inputs {
    FileAcquisitionCase source;FileImageVerification verification;
    Inputs(const std::string& id,const std::string& directory,const std::string& image,const std::string& map):source(id,directory),
        verification(acquisition::prepare(field(field(field(source.report().view(),"before"),"definition"),"plan")),image,map) {}
    explicit Inputs(const V& d):Inputs(text(d,"case_operation_id"),text(field(field(d,"case_source"),"store"),"path"),
        text(field(field(d,"image_binding"),"image"),"path"),text(field(field(d,"image_binding"),"map"),"path")) {
        if(encode(source.binding())!=encode(field(d,"case_source")) || source.request_bytes()!=text(d,"request_raw") ||
           encode(verification.binding())!=encode(field(d,"image_binding")) || verification.definition().digest!=text(d,"verification_digest"))reject("verification_worker_input_changed");
    }
};
V reply(const char* status,const std::string& id,V value,const std::string& diagnostic="",DWORD platform=0) {
    return V::object().put("schema",V::string("org.disked.verification-admission-prototype/1")).put("status",V::string(status))
        .put("operation_id",id.empty()?V{}:V::string(id)).put("value",value).put("diagnostic",V::string(diagnostic)).put("platform_code",number(platform));
}
V header_read(const Directory& dir) {
    auto file=dir.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!file.valid())fail("verification_worker_request_unavailable");
    const auto raw=read_file(file.value,r::header_limit);const auto h=json::parse(raw,r::definition_limits());r::validate_header(h);
    if(raw!=encode(h))reject("verification_worker_request_noncanonical");return h;
}
V observer(const V& binding) {
    auto v=V::object();for(const auto n:{"attempt_id","worker_epoch","capture_epoch","process_id","process_created"})v.put(n,field(binding,n));return v;
}
std::string collection_check(const std::string& bytes,const V& state,const V& header) {
    const auto collection=e::ImageVerificationCollection::restore(bytes);const auto& retained=field(state,"retention");const auto& view=collection.view();
    if(e::export_digest(bytes)!=text(retained,"digest") || bytes.size()!=integer(field(retained,"bytes")) || collection.revision()!=text(retained,"collection_revision") ||
       text(view,"collection_id")!="collection:"+text(header,"operation_id").substr(10) || field(view,"records").items.size()!=1 ||
       text(view,"request_raw")!=text(field(header,"definition"),"request_raw") || text(view,"case_revision")!=text(field(field(header,"definition"),"case_source"),"case_revision"))reject("verification_worker_collection_binding");
    const auto& row=field(view,"records").items.front();const auto& observation=field(row,"observation");const auto& d=field(header,"definition");
    if(text(row,"observation_revision")!=text(retained,"observation_revision") || encode(field(row,"observer"))!=encode(observer(field(state,"binding"))) ||
       encode(field(observation,"outcome"))!=encode(field(state,"outcome")) || encode(field(observation,"definition"))!=encode(field(d,"verification")) ||
       encode(field(observation,"verifier"))!=encode(field(d,"verifier")) || encode(field(observation,"case_source_before"))!=encode(field(d,"case_source")) ||
       encode(field(observation,"image_binding_before"))!=encode(field(d,"image_binding")))reject("verification_worker_collection_binding");
    return text(observation,"attachment_applicability");
}
V inspect(const std::string& id,const Directory& dir,const V& h,r::History* captured=nullptr) {
    if(text(h,"operation_id")!=id)reject("verification_worker_identity");Security security;
    if(text(field(h,"definition"),"host_id")!=security.host_id || encode(field(field(h,"definition"),"store"))!=encode(store_binding(dir)))reject("verification_worker_identity");
    auto value=V::object().put("definition",field(h,"definition")).put("definition_digest",field(h,"definition_digest"));
    try {
        auto file=dir.open(records_name,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid() || file_identity(file.value)!=text(h,"records_id"))reject("verification_worker_history_identity");
        const auto history=r::read_history(read_file(file.value,r::history_limit),h);if(captured)*captured=history;
        value.put("state",history.state).put("request_binding",r::expected_binding(h)).put("last_digest",V::string(history.previous)).put("history_complete",V::boolean_value(history.complete));
        const auto& binding=field(history.state,"binding");const auto pid=static_cast<DWORD>(integer(field(binding,"process_id")));
        Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid));std::string observed="unavailable";
        if(process.valid()) {
            if(process_created(process.value)!=text(binding,"process_created"))observed="reused_identity";
            else if(WaitForSingleObject(process.value,0)==WAIT_OBJECT_0)observed="exited";
            else if(WaitForSingleObject(process.value,0)==WAIT_TIMEOUT) {
                wchar_t path[32768];DWORD length=32768;
                if(QueryFullProcessImageNameW(process.value,0,path,&length))observed=CompareStringOrdinal(path,static_cast<int>(length),wide(text(field(h,"definition"),"worker_image_path")).c_str(),-1,TRUE)==CSTR_EQUAL?"running":"changed_image_path";
            }
        }else if(GetLastError()==ERROR_INVALID_PARAMETER)observed="exited";
        value.put("worker_observation",V::string(observed));
        if(text(field(history.state,"retention"),"state")=="verified") {
            auto collection=dir.open(collection_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);
            if(!collection.valid() || file_identity(collection.value)!=text(h,"collection_id"))reject("verification_worker_collection_identity");
            const auto attachment=collection_check(read_file(collection.value,1048577),history.state,h);
            value.put("collection_validation",V::string("passed")).put("attachment_applicability",V::string(attachment));
        }
        if(!history.complete)return reply("unknown",id,value,"verification_worker_history_torn");
        if(text(history.state,"phase")!="finished" && observed!="running")return reply("unknown",id,value,"verification_worker_unresolved");
        return reply("completed",id,value);
    }catch(const std::exception& error) {return reply("unknown",id,value,error.what());}
}
V counts(const e::VerificationOutcome* o=nullptr) {
    auto value=V::object();const auto view=o?o->view():V{};
    for(const auto n:{"records","consumed_map_bytes","covered_bytes","read_bytes","source_bytes","substituted_bytes"})value.put(n,o?field(view,n):number(0));return value;
}
struct Recorder {
    HANDLE file;const V& header;r::History history;
    void save(V state,const char* point) {
        if(history.count>=r::record_count_limit || file_size(file)>r::history_limit-r::record_limit-1)reject("verification_worker_history_limit");
        FILETIME now{};GetSystemTimeAsFileTime(&now);state.put("sequence",number(history.count+1)).put("observed_filetime",number(file_time(now)));
        r::validate_state(state,header,history.count+1);if(history.count)r::validate_progress(history.state,state);
        auto row=V::object().put("schema",V::string("org.disked.verification-worker-record-prototype/1")).put("state",state).put("previous",V::string(history.previous));
        const auto hash_value=hash(json::dump(row,r::row_limits()));row.put("digest",V::string(hash_value));
        write_file(file,json::dump(row,r::row_limits())+'\n',point);history.state=state;history.previous=hash_value;++history.count;
    }
};
#ifdef DISKED_VERIFICATION_WORKER_TESTING
void delay(const wchar_t* key) {if(GetEnvironmentVariableW(key,nullptr,0))Sleep(5000);}
#else
void delay(const wchar_t*) {}
#endif
}
V prepare_verification_worker(const std::string& id,const std::string& directory,const std::string& image_path,const std::string& map,const std::string& execution_directory) {
    Directory dir(execution_directory);dir.empty();Security security;Image image;Inputs inputs(id,directory,image_path,map);
    auto d=V::object().put("schema",V::string("org.disked.verification-worker-definition-prototype/1")).put("case_operation_id",V::string(id))
        .put("case_source",inputs.source.binding()).put("request_raw",V::string(inputs.source.request_bytes())).put("verification",inputs.verification.definition().value)
        .put("verification_digest",V::string(inputs.verification.definition().digest)).put("image_binding",inputs.verification.binding()).put("store",store_binding(dir))
        .put("host_id",V::string(security.host_id)).put("verifier",code(image)).put("worker_image_path",V::string(narrow(image.path)));
    r::validate_definition(d);return V::object().put("definition",d).put("definition_digest",V::string(r::digest(d)));
}
V start_verification_worker(const V& d,const V& g) {
    std::string id;bool claimed=false,existing=false;
    try {
        r::validate_definition(d);r::validate_grant(g,d);Directory dir(text(field(d,"store"),"path"));Security security;Image image;
        Directory code_parent(narrow(image.path.substr(0,image.path.find_last_of(L'\\'))));applicable(d,dir,security,image);
        if(GetFileAttributesW(dir.child(request_name).c_str())!=INVALID_FILE_ATTRIBUTES) {
            existing=true;const auto h=header_read(dir);id=text(h,"operation_id");
            if(text(h,"definition_digest")!=r::digest(d) || encode(field(h,"grant"))!=encode(g))reject("verification_worker_existing_definition_conflict");
            auto out=inspect(id,dir,h);if(text(out,"status")=="completed" && text(field(field(out,"value"),"state"),"phase")!="finished")out.put("status",V::string("accepted_running"));return out;
        }
        dir.empty();{Inputs reviewed(d);}
        ULARGE_INTEGER free{};if(!GetDiskFreeSpaceExW(dir.path.c_str(),&free,nullptr,nullptr))fail("verification_worker_capacity_observation");
        if(free.QuadPart<r::history_limit+r::header_limit+1048577)reject("verification_worker_capacity");auto attributes=security.attributes;id=security.identity("verify-op:");
        auto lock=dir.open(lock_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes,&claimed);if(!lock.valid())fail("verification_worker_busy");
        auto records=dir.open(records_name,GENERIC_READ|FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);if(!records.valid())fail("verification_worker_store_create");
        auto cancel=dir.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,CREATE_NEW,&attributes);if(!cancel.valid())fail("verification_worker_store_create");write_file(cancel.value,"0","verification_cancel_create");
        auto collection=dir.open(collection_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,CREATE_NEW,&attributes);if(!collection.valid())fail("verification_worker_store_create");
        auto h=V::object().put("schema",V::string("org.disked.verification-worker-request-prototype/1")).put("operation_id",V::string(id)).put("worker_epoch",V::string(security.identity("worker:")))
            .put("attempt_id",V::string(security.identity("attempt:"))).put("capture_epoch",V::string(security.identity("capture:"))).put("definition",d).put("definition_digest",V::string(r::digest(d))).put("grant",g)
            .put("records_id",V::string(file_identity(records.value))).put("cancel_id",V::string(file_identity(cancel.value))).put("collection_id",V::string(file_identity(collection.value)));r::validate_header(h);
        auto output=dir.open(request_name,GENERIC_WRITE,0,CREATE_NEW,&attributes);if(!output.valid())fail("verification_worker_store_create");write_file(output.value,encode(h),"verification_request");output=Handle();
        auto input=dir.open(request_name,GENERIC_READ,FILE_SHARE_READ,OPEN_EXISTING);if(!input.valid() || read_file(input.value,r::header_limit)!=encode(h))reject("verification_worker_request_changed");
        Handle event(CreateEventW(&attributes,TRUE,FALSE,nullptr));if(!event.valid())fail("verification_worker_event_create");
        auto ci=inherited(input.value,GENERIC_READ),cr=inherited(records.value,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES),cc=inherited(cancel.value,GENERIC_READ),ce=inherited(event.value,EVENT_MODIFY_STATE|SYNCHRONIZE),co=inherited(collection.value,GENERIC_READ|GENERIC_WRITE);
        std::vector<HANDLE> handles={ci.value,cr.value,cc.value,ce.value,co.value};WorkerBudget aggregate(security,true);Handle job(CreateJobObjectW(&attributes,nullptr));if(!job.valid())fail("verification_worker_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
        if(!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("verification_worker_job_limits");std::vector<HANDLE> jobs={aggregate.job.value,job.value};AttributeList list(handles,jobs);
        STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=list.list;
        startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
        std::wstring command=L"\""+image.path+L"\" __disked_verification_worker";for(const auto handle:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(handle));
        dir.check();code_parent.check();PROCESS_INFORMATION raw{};
        if(!CreateProcessW(image.path.c_str(),&command[0],nullptr,nullptr,TRUE,DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,dir.path.c_str(),&startup.StartupInfo,&raw))fail("verification_worker_spawn_failed");
        Handle process(raw.hProcess),thread(raw.hThread);ci=Handle();cr=Handle();cc=Handle();ce=Handle();co=Handle();input=Handle();records=Handle();cancel=Handle();collection=Handle();
        HANDLE waits[]={event.value,process.value};const auto wait=WaitForMultipleObjects(2,waits,FALSE,3000);
        if(wait!=WAIT_OBJECT_0)return reply("unknown",id,V::object().put("admission",V::string("unresolved")),"verification_worker_admission_unresolved");
        auto out=inspect(id,dir,h);if(text(out,"status")=="completed" && text(field(field(out,"value"),"state"),"phase")!="finished")out.put("status",V::string("accepted_running"));return out;
    }catch(const Failure& error) {return reply(claimed||existing?"unknown":"refused",claimed||existing?id:"",V::object(),error.what(),error.platform);}
     catch(const std::exception& error) {return reply(claimed||existing?"unknown":"refused",claimed||existing?id:"",V::object(),error.what());}
}
V observe_verification_worker(const std::string& id,const std::string& directory,bool cancel_request) {
    try {
        identifier(id);Directory dir(directory);const auto h=header_read(dir);auto out=inspect(id,dir,h);
        if(cancel_request && field(out,"value").find("state") && field(field(out,"value"),"state").kind==V::Kind::object) {
            auto& value=out.fields["value"];
            if(text(field(value,"state"),"phase")=="finished")value.put("cancellation_request",V::string("too_late"));
            else {
                auto file=dir.open(cancel_name,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);if(!file.valid() || file_identity(file.value)!=text(h,"cancel_id"))reject("verification_worker_cancel_identity");
                const auto flag=read_file(file.value,1);if(flag!="0" && flag!="1")reject("verification_worker_cancel_invalid");LARGE_INTEGER zero{};if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))fail("verification_worker_cancel_seek");
                write_file(file.value,"1","verification_cancel_request");value.put("cancellation_request",V::string("requested"));
            }
        }
        return out;
    }catch(const Failure& error) {return reply("unknown",id,V::object(),error.what(),error.platform);}
     catch(const std::exception& error) {return reply("unknown",id,V::object(),error.what());}
}
V watch_verification_worker(const std::string& id,const std::string& directory,const std::string& sequence,const std::string& after,const std::string& worker) {
    identifier(id);if(!json::decimal_u64(sequence) || std::stoull(sequence)>r::record_count_limit)reject("verification_watch_cursor");
    Directory dir(directory);const auto h=header_read(dir);r::History history;auto out=inspect(id,dir,h,&history);const auto n=static_cast<std::size_t>(std::stoull(sequence));
    if(!history.count) return out;
    if((n==0 && (after!=std::string(64,'0') || !worker.empty())) || n>history.count || (n && (text(history.records[n-1],"digest")!=after || text(h,"worker_epoch")!=worker)))reject("verification_watch_cursor");
    auto records=V::array();for(std::size_t i=n;i<history.count;++i)records.items.push_back(history.records[i]);
    out.fields["value"].put("records",records).put("last_sequence",number(history.count)).put("last_digest",V::string(history.previous)).put("worker_epoch",field(h,"worker_epoch"));return out;
}
namespace {
bool operation_parameters(const V& p,bool watch) {
    if(p.kind!=V::Kind::object)return false;
    const std::set<std::string> keys=watch?std::set<std::string>{"operation_id","state_directory","after_sequence","after_digest","worker_epoch","follow_ms","snapshot"}:std::set<std::string>{"operation_id","state_directory"};
    for(const auto& pair:p.fields)if(!keys.count(pair.first))return false;
    const auto id=p.find("operation_id"),dir=p.find("state_directory");if(!id || id->kind!=V::Kind::string || !dir || dir->kind!=V::Kind::string || dir->text.size()<3 || dir->text.size()>960 ||
       !json::valid_utf8(dir->text) || !((dir->text[0]>='A' && dir->text[0]<='Z') || (dir->text[0]>='a' && dir->text[0]<='z')) || dir->text[1]!=':' || dir->text[2]!='\\')return false;
    try {identifier(id->text);}catch(const std::exception&) {return false;}return true;
}
Outcome unknown_watch(const std::string& request,const std::string& id,V last,const std::string& code,DWORD platform=0) {
    last.put("scope",V::string("recorded-acquired-image-verification")).put("request_kind",V::string("operation-observation"))
        .put("authenticity",V::string("not_established")).put("latest_image_state",V::string("not_established")).put("source_preservation",V::string("not_established"))
        .put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));if(!last.find("events"))last.put("events",V::array());
    auto out=completed(request,last);out.exit_code=6;out.response.put("status",V::string("unknown")).put("operation_id",id.empty()?V{}:V::string(id));
    auto d=diagnostic(code);if(platform)d.put("platform_code",V::string(std::to_string(platform)));out.response.fields["diagnostics"].items.push_back(d);return out;
}
}
Outcome watch_verification_operation(const std::string& request,const V& p,const std::shared_ptr<WatchQueue>& events) {
    if(!operation_parameters(p,true))return refused(request,"invalid_parameter");const auto invalid=validate_watch_parameters(p);if(!invalid.empty())return refused(request,invalid);
    const auto id=text(p,"operation_id");auto last=V::object().put("state_directory",field(p,"state_directory"));
    try {
        Directory dir(text(p,"state_directory"));const auto header=header_read(dir);Security security;if(text(header,"operation_id")!=id)reject("verification_worker_identity");
        const auto observer=security.identity("watch:");WatchCursor cursor(id,request,observer,p,verification_watch_profile(header));
        auto collected=V::array();V validated_state;std::size_t bytes=0,delivered=0;const auto follow=p.find("follow_ms");const auto end=GetTickCount64()+(follow?std::stoull(follow->text):0);
        for(;;) {
#ifdef DISKED_VERIFICATION_WORKER_TESTING
            if(delivered && GetEnvironmentVariableW(L"DISKED_VERIFICATION_WATCH_TEST_READ_FAILURE",nullptr,0))reject("verification_watch_test_read_failure");
#endif
            r::History history;auto out=verification_observation(request,inspect(id,dir,header,&history));std::vector<V> batch;auto candidate=cursor;auto next=collected;std::size_t added=0;
            if(history.count) {
                try {batch=candidate.project(history.state,history.records,history.previous);}catch(const std::invalid_argument& error) {return refused(request,error.what());}
                for(const auto& item:batch) {const auto size=json::dump(item,watch_event_limits(item)).size();if(size>786432-bytes-added)throw std::invalid_argument("watch_queue_limit");added+=size;}
                if(batch.size()>64-delivered)throw std::invalid_argument("watch_queue_limit");if(!events)for(const auto& item:batch)next.items.push_back(item);
            }
            auto pending=out;auto& value=pending.response.fields["result"];if(value.kind!=V::Kind::object)value=V::object();
            value.put("state_directory",field(p,"state_directory")).put("observer_epoch",V::string(observer)).put("last_sequence",V::string(candidate.sequence())).put("last_digest",V::string(candidate.digest()))
                .put("worker_epoch",candidate.worker().empty()?V{}:V::string(candidate.worker())).put("events",events?V::array():next);
            if(!history.count && validated_state.kind!=V::Kind::null)value.put("last_validated_state",validated_state);
            auto limits=response_limits(pending.response);limits.bytes-=2048;limits.values-=128;json::dump(pending.response,limits);
            for(const auto& item:batch)if(events && !events->push(item))return out;
            cursor=std::move(candidate);collected=std::move(next);bytes+=added;delivered+=batch.size();if(history.count)validated_state=history.state;
            out=std::move(pending);last=out.response.fields["result"];if(out.exit_code || (history.count && text(history.state,"phase")=="finished"))return out;
            if(GetTickCount64()>=end) {out.response.put("status",V::string("accepted_running"));out.exit_code=5;return out;}Sleep(25);
        }
    }catch(const Failure& error) {return unknown_watch(request,id,last,error.what(),error.platform);}
     catch(const std::exception& error) {return unknown_watch(request,id,last,error.what());}
}
VerificationActions verification_actions() {
    VerificationActions ports;ports.prepare=[](const V& p) {return prepare_verification_worker(text(p,"case_operation_id"),text(p,"case_directory"),text(p,"image"),text(p,"map"),text(p,"state_directory"));};
    ports.execute=start_verification_worker;return ports;
}
Outcome dispatch_verification_operation(const std::string& request,const std::string& command,const V& p) {
    if(command=="operation.watch")return watch_verification_operation(request,p);
    if(command!="operation.inspect" && command!="operation.cancel.request")return refused(request,"command_unavailable",3);
    if(!operation_parameters(p,false))return refused(request,"invalid_parameter");return verification_observation(request,observe_verification_worker(text(p,"operation_id"),text(p,"state_directory"),command=="operation.cancel.request"));
}
int run_verification_worker(int argc,wchar_t** argv) {
    try {
        if(argc!=7)reject("verification_worker_role_arguments");std::vector<HANDLE> capabilities;for(int i=2;i<7;++i)capabilities.push_back(argument_handle(argv[i]));
        for(std::size_t i=0;i<capabilities.size();++i)for(std::size_t j=0;j<i;++j)if(capabilities[i]==capabilities[j])reject("verification_worker_role_capability");
        Handle input(capabilities[0]),records(capabilities[1]),cancel(capabilities[2]),event(capabilities[3]),collection(capabilities[4]);for(const auto h:capabilities)if(!SetHandleInformation(h,HANDLE_FLAG_INHERIT,0))reject("verification_worker_role_capability");
        for(const auto channel:{STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE}) {DWORD flags=0;const auto h=GetStdHandle(channel);if(h && h!=INVALID_HANDLE_VALUE && GetHandleInformation(h,&flags))reject("verification_worker_role_standard_handle");}
        if(file_size(records.value)!=0 || file_size(cancel.value)!=1 || file_size(collection.value)!=0 || WaitForSingleObject(event.value,0)!=WAIT_TIMEOUT)reject("verification_worker_role_capability");
        const auto path=final_path(input.value);const auto slash=path.find_last_of(L'\\');const auto parent=path.substr(0,slash+1);
        if(path.compare(0,4,L"\\\\?\\") || path.substr(slash+1)!=request_name || final_path(records.value)!=parent+records_name || final_path(cancel.value)!=parent+cancel_name || final_path(collection.value)!=parent+collection_name)reject("verification_worker_role_capability");
        Directory dir(narrow(parent.substr(4,parent.size()-5)));const auto h=json::parse(read_file(input.value,r::header_limit),r::definition_limits());const auto persisted=header_read(dir);
        if(encode(h)!=encode(persisted) || text(h,"records_id")!=file_identity(records.value) || text(h,"cancel_id")!=file_identity(cancel.value) || text(h,"collection_id")!=file_identity(collection.value))reject("verification_worker_role_capability");
        Security security;Image image;applicable(field(h,"definition"),dir,security,image);WorkerBudget aggregate(security,false);JOBOBJECT_EXTENDED_LIMIT_INFORMATION budget{};
        if(!QueryInformationJobObject(nullptr,JobObjectExtendedLimitInformation,&budget,sizeof(budget),nullptr) || budget.BasicLimitInformation.ActiveProcessLimit!=1 || budget.ProcessMemoryLimit!=128*1024*1024 ||
           budget.BasicLimitInformation.LimitFlags!=(JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY))reject("verification_worker_role_budget");
        auto binding=r::expected_binding(h);binding.put("process_id",number(GetCurrentProcessId())).put("process_created",V::string(process_created(GetCurrentProcess())));
        auto state=V::object().put("schema",V::string("org.disked.verification-worker-state-prototype/1")).put("binding",binding).put("sequence",number(0)).put("phase",V::string("prepared"))
            .put("cancellation_observation",V::string("not_observed")).put("observed_filetime",number(0)).put("quiescent",V::boolean_value(false)).put("disposition",V::string("running"))
            .put("progress",counts()).put("outcome",V{}).put("diagnostic",V::string(""))
            .put("retention",V::object().put("state",V::string("empty")).put("bytes",number(0)).put("digest",V{}).put("collection_revision",V{}).put("observation_revision",V{}).put("flush",V::string("not_attempted")));
        Recorder recorder{records.value,h,r::History{}};recorder.save(state,"verification_prepared");std::unique_ptr<Inputs> inputs;bool has_outcome=false;
        const auto stop=[&] {
            const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")reject("verification_worker_cancel_invalid");
            if(flag=="1" && text(state,"cancellation_observation")=="not_observed") {state.put("cancellation_observation",V::string("observed"));recorder.save(state,"verification_cancel_observed");}
            return flag=="1";
        };
        try {
            delay(L"DISKED_VERIFICATION_WORKER_TEST_ADMISSION_DELAY");
            if(stop())state.put("disposition",V::string("cancelled"));
            else {
                inputs.reset(new Inputs(field(h,"definition")));if(!SetEvent(event.value))fail("verification_worker_admission_signal");event=Handle();
                delay(L"DISKED_VERIFICATION_WORKER_TEST_EFFECT_DELAY");state.put("phase",V::string("verifying"));recorder.save(state,"verification_verifying");
                FILETIME started{};GetSystemTimeAsFileTime(&started);const auto ticks=GetTickCount64();std::size_t sampled=0;const auto& d=inputs->verification.definition();
                const auto o=inputs->verification.execute({d.digest,true,true},stop,[&](const e::VerificationOutcome& progress) {
                    if(sampled<12 && progress.covered_bytes>=((d.plan.bytes/12)*sampled+(d.plan.bytes%12)*sampled/12)) {
                        state.put("progress",counts(&progress));recorder.save(state,"verification_progress");++sampled;if(sampled==1)delay(L"DISKED_VERIFICATION_WORKER_TEST_PROGRESS_DELAY");
                    }
                });
                // Freeze the actual verdict before collection effects or any late request.
                has_outcome=true;state.put("outcome",o.view()).put("progress",counts(&o));
                FILETIME finished{};GetSystemTimeAsFileTime(&finished);const auto& definition=field(h,"definition");
                auto context=V::object().put("verifier",field(definition,"verifier")).put("case_before",field(definition,"case_source")).put("image_before",field(definition,"image_binding"));
                try {inputs->source.check();context.put("case_after",inputs->source.binding()).put("case_revalidation",V::string("passed"));}
                catch(const std::exception&) {context.put("case_after",V{}).put("case_revalidation",V::string("unavailable"));}
                try {const auto after=inputs->verification.binding();context.put("image_after",after).put("image_binding_revalidation",V::string(encode(after)==encode(field(definition,"image_binding"))?"passed":"changed"));}
                catch(const std::exception&) {context.put("image_after",V{}).put("image_binding_revalidation",V::string("unavailable"));}
                context.put("clock",V::object().put("domain",V::string("windows-filetime-wall")).put("started",number(file_time(started))).put("finished",number(file_time(finished))).put("elapsed_ms",number(GetTickCount64()-ticks)));
                const e::ImageVerificationObservation observation(inputs->source.report(),inputs->source.request_bytes(),d,o,context);
                const auto retained=e::ImageVerificationCollection("collection:"+text(h,"operation_id").substr(10),inputs->source.report(),inputs->source.request_bytes(),inputs->source.history_bytes()).with_observation(observation,observer(binding));
                const e::CollectionRetentionArtifact artifact(retained);state.put("phase",V::string("persisting"));auto& retention=state.fields["retention"];
                retention.put("state",V::string("in_flight")).put("digest",V::string(artifact.digest())).put("collection_revision",V::string(retained.revision())).put("observation_revision",V::string(observation.revision()));
                recorder.save(state,"verification_persisting");delay(L"DISKED_VERIFICATION_WORKER_TEST_RETENTION_DELAY");
                retention.put("flush",V::string("uncertain"));write_file(collection.value,artifact.bytes(),"verification_collection");retention.put("flush",V::string("api_confirmed"));
                const auto read=read_file(collection.value,1048577);if(read!=artifact.bytes())reject("verification_worker_collection_readback");e::ImageVerificationCollection::restore(read);
                retention.put("state",V::string("verified")).put("bytes",number(read.size()));
                state.put("disposition",V::string(o.status=="cancelled"?"cancelled":o.status=="unknown"?"unknown":"completed"));
            }
        }catch(const std::exception& error) {
            const std::string message=error.what();state.put("diagnostic",V::string(message.size()<=128 && message.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")==message.npos?message:"verification_worker_unavailable"));
            state.put("disposition",V::string(has_outcome?"unknown":"refused"));
            if(has_outcome) {auto& retention=state.fields["retention"];retention.put("state",V::string("uncertain"));try {retention.put("bytes",number(file_size(collection.value)));}catch(...) {retention.put("bytes",V{});}}
        }
        inputs.reset();collection=Handle(); // Release selected providers and collection before quiescence.
        state.put("phase",V::string("finished")).put("quiescent",V::boolean_value(true));recorder.save(state,"verification_finished");if(event.valid())SetEvent(event.value);return 0;
    }catch(...) {return 199;}
}
}
