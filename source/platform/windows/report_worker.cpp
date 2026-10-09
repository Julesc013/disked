#include "report_worker.h"
#include "file_acquisition_export.h"
#include "file_verification_case_export.h"
#include "worker_files.h"
#include "bootstrap_registry.h"
#include "report_observation.h"
#include <set>
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
    const auto& source=r::joined_definition(d)?field(field(joint,"sources"),"case"):field(joint,"source");
    if(encode(field(field(source,"store"),"generation"))==encode(local_file::generation(dir.pinned.back().value,true)))reject("report_worker_source_store_alias");
    if(r::joined_definition(d)) {
        const auto selected=local_file::path_for(text(field(field(joint,"sources"),"collection"),"path"));
        for(const auto name:{request_name,records_name,cancel_name,lock_name})if(CompareStringOrdinal(selected.c_str(),-1,dir.child(name).c_str(),-1,TRUE)==CSTR_EQUAL)reject("report_worker_collection_store_alias");
    }
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
struct ReportResult {V outcome,receipt;};
class ReportSession {
public:
    virtual ~ReportSession()=default;
    virtual ReportResult execute(const std::function<bool()>& stop)=0;
};
class AcquisitionSession final:public ReportSession {
    FileAcquisitionExport effect_;
public:
    explicit AcquisitionSession(const V& joint):effect_(text(field(joint,"case"),"operation_id"),text(field(field(joint,"source"),"store"),"path"),
        field(field(field(joint,"effect"),"artifact"),"policy"),text(field(field(field(joint,"effect"),"resources"),"destination"),"location"),&joint) {}
    ReportResult execute(const std::function<bool()>& stop) override {
        const auto result=effect_.execute({effect_.definition().digest(),true,true,true},stop);return {result.outcome.view(),result.receipt};
    }
};
class JoinedSession final:public ReportSession {
    FileVerificationCaseExport effect_;
public:
    explicit JoinedSession(const V& joint):effect_(text(field(joint,"report"),"case_operation_id"),text(field(field(field(joint,"sources"),"case"),"store"),"path"),
        text(field(field(joint,"sources"),"collection"),"path"),text(field(field(joint,"sources"),"collection"),"digest"),
        field(field(field(joint,"effect"),"artifact"),"policy"),text(field(field(field(joint,"effect"),"resources"),"destination"),"location"),&joint) {}
    ReportResult execute(const std::function<bool()>& stop) override {
        const auto result=effect_.execute({effect_.definition().digest(),true,true,true,true},stop);return {result.outcome.view(),result.receipt};
    }
};
std::unique_ptr<ReportSession> reconstruct(const V& d) {
    const auto& joint=field(d,"export");if(r::joined_definition(d))return std::unique_ptr<ReportSession>(new JoinedSession(joint));
    return std::unique_ptr<ReportSession>(new AcquisitionSession(joint));
}
V prepared_definition(const V& joint,const Directory& dir,const Security& security,const Image& image,bool joined) {
    auto d=V::object().put("schema",V::string(joined?"org.disked.report-worker-definition-prototype/2":"org.disked.report-worker-definition-prototype/1")).put("export",joint)
        .put("store",store_binding(dir)).put("host_id",V::string(security.host_id)).put("image_digest",V::string(image.digest))
        .put("source_revision",V::string(bootstrap::source_revision)).put("input_digest",V::string(bootstrap::input_digest)).put("target_profile",V::string(bootstrap::target));
    r::validate_definition(d);no_alias(d,dir);const auto digest=r::digest(d);
    auto grant=V::object().put("definition_digest",V::string(digest)).put("case_read",V::boolean_value(true)).put("report_write",V::boolean_value(true))
        .put("store_write",V::boolean_value(true)).put("host_effects",V::boolean_value(true));if(joined)grant.put("collection_read",V::boolean_value(true));
    // All actual identities have these fixed widths. Maximum file identity
    // decimal widths bound the complete retained header before any claim.
    const auto projection=V::object().put("schema",V::string("org.disked.report-worker-request-prototype/1")).put("operation_id",V::string("report-op:"+std::string(32,'0')))
        .put("worker_epoch",V::string("worker:"+std::string(32,'0'))).put("attempt_id",V::string("attempt:"+std::string(32,'0'))).put("definition",d)
        .put("definition_digest",V::string(digest)).put("grant",grant).put("records_id",V::string("18446744073709551615:18446744073709551615"))
        .put("cancel_id",V::string("18446744073709551615:18446744073709551614"));r::validate_header(projection);
    return V::object().put("definition",d).put("definition_digest",V::string(digest));
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
V inspect(const std::string& id,const Directory& dir,const V& h,r::History* captured=nullptr) {
    if(text(h,"operation_id")!=id)reject("report_worker_identity");Security security;
    // Compatible historical observation does not require the current executable
    // or the original read/output resources to remain applicable for execution.
    if(text(field(h,"definition"),"host_id")!=security.host_id || encode(field(field(h,"definition"),"store"))!=encode(store_binding(dir)))reject("report_worker_identity");
    auto value=V::object().put("definition",field(h,"definition")).put("definition_digest",field(h,"definition_digest"));
    try {
        auto file=dir.open(records_name,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,OPEN_EXISTING);
        if(!file.valid() || file_identity(file.value)!=text(h,"records_id"))reject("report_worker_history_identity");
        const auto history=r::read_history(read_file(file.value,r::history_limit),h);
        if(captured)*captured=history;
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
    return prepared_definition(session.definition().value(),dir,security,image,false);
}
V prepare_joined_report_worker(const std::string& id,const std::string& case_dir,const std::string& collection,const std::string& digest,
    const V& policy,const std::string& destination,const std::string& execution_dir) {
    Directory dir(execution_dir);dir.empty();Security security;Image image;FileVerificationCaseExport session(id,case_dir,collection,digest,policy,destination);
    return prepared_definition(session.definition().value(),dir,security,image,true);
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
V observe_report_worker(const std::string& id,const std::string& directory,bool cancel_request,bool common_profile) {
    try {
        identifier(id);Directory dir(directory);const auto h=header_read(dir);
        if(common_profile && r::joined_definition(field(h,"definition")))return reply("refused","",V::object(),"report_worker_profile_unavailable");
        auto observed=inspect(id,dir,h);
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
namespace {
bool operation_parameters(const V& p,bool watch) {
    if(p.kind!=V::Kind::object)return false;
    const std::set<std::string> keys=watch?std::set<std::string>{"operation_id","state_directory","after_sequence","after_digest","worker_epoch","follow_ms","snapshot"}:std::set<std::string>{"operation_id","state_directory"};
    for(const auto& pair:p.fields)if(!keys.count(pair.first))return false;
    const auto id=p.find("operation_id"),dir=p.find("state_directory");
    if(!id || id->kind!=V::Kind::string || !dir || dir->kind!=V::Kind::string || dir->text.size()<3 || dir->text.size()>960 ||
       !json::valid_utf8(dir->text) || !((dir->text[0]>='A' && dir->text[0]<='Z') || (dir->text[0]>='a' && dir->text[0]<='z')) || dir->text[1]!=':' || dir->text[2]!='\\')return false;
    try {identifier(id->text);}catch(const std::exception&) {return false;}return true;
}
Outcome unknown_watch(const std::string& request,const std::string& id,V last,const std::string& code,DWORD platform=0) {
    last.put("scope",V::string("recorded-acquisition-case-support-export")).put("request_kind",V::string("operation-observation"))
        .put("authenticity",V::string("not_established")).put("current_image_verification",V::string("not_performed"));
    if(!last.find("events"))last.put("events",V::array());
    auto out=completed(request,last);out.exit_code=6;out.response.put("status",V::string("unknown")).put("operation_id",id.empty()?V{}:V::string(id));
    auto d=diagnostic(code);if(platform)d.put("platform_code",V::string(std::to_string(platform)));out.response.fields["diagnostics"].items.push_back(d);return out;
}
}
Outcome watch_report_worker(const std::string& request,const V& parameters,const std::shared_ptr<WatchQueue>& events) {
    if(!operation_parameters(parameters,true))return refused(request,"invalid_parameter");
    const auto invalid=validate_watch_parameters(parameters);if(!invalid.empty())return refused(request,invalid);
    const auto id=text(parameters,"operation_id");auto last=V::object().put("state_directory",field(parameters,"state_directory"));
    try {
        Directory dir(text(parameters,"state_directory"));const auto header=header_read(dir);Security security;
        if(text(header,"operation_id")!=id)reject("report_worker_identity");
        if(r::joined_definition(field(header,"definition")))return refused(request,"report_worker_profile_unavailable",3);
        const auto observer=security.identity("watch:");WatchCursor cursor(id,request,observer,parameters,report_watch_profile(header));
        auto collected=V::array();V validated_state;std::size_t bytes=0,delivered=0;
        const auto follow=parameters.find("follow_ms");const auto end=GetTickCount64()+(follow?std::stoull(follow->text):0);
        for(;;) {
#ifdef DISKED_REPORT_WORKER_TESTING
            // Test only: lose a later observer read without touching the live
            // worker, its capabilities or its append-only history.
            if(delivered && GetEnvironmentVariableW(L"DISKED_REPORT_WATCH_TEST_READ_FAILURE",nullptr,0))reject("report_watch_test_read_failure");
#endif
            r::History history;auto observed=inspect(id,dir,header,&history);auto out=export_observation(request,observed);
            std::vector<V> batch;auto candidate=cursor;auto next_collected=collected;std::size_t added=0;
            if(history.count) {
                try {batch=candidate.project(history.state,history.records,history.previous);}
                catch(const std::invalid_argument& error) {return refused(request,error.what());}
                for(const auto& item:batch) {
                    const auto size=json::dump(item,watch_event_limits(item)).size();
                    if(size>786432-bytes-added)throw std::invalid_argument("watch_queue_limit");added+=size;
                }
                if(batch.size()>64-delivered)throw std::invalid_argument("watch_queue_limit");
                if(!events)for(const auto& item:batch)next_collected.items.push_back(item);
            }
            auto pending=out;auto& value=pending.response.fields["result"];if(value.kind!=V::Kind::object)value=V::object();
            value.put("state_directory",field(parameters,"state_directory")).put("observer_epoch",V::string(observer))
                .put("last_sequence",V::string(candidate.sequence())).put("last_digest",V::string(candidate.digest()))
                .put("worker_epoch",candidate.worker().empty()?V{}:V::string(candidate.worker()));
            if(!history.count && validated_state.kind!=V::Kind::null)value.put("last_validated_state",validated_state);
            value.put("events",events?V::array():next_collected);
            // Check the whole proposed reply before publishing any new cursor
            // or queue batch. Keep room for a later bounded unknown diagnostic.
            auto limits=response_limits(pending.response);limits.bytes-=2048;limits.values-=128;json::dump(pending.response,limits);
            for(const auto& item:batch)if(events && !events->push(item))return out;
            cursor=std::move(candidate);collected=std::move(next_collected);bytes+=added;delivered+=batch.size();
            if(history.count)validated_state=history.state;
            out=std::move(pending);last=out.response.fields["result"];
            if(out.exit_code || (history.count && text(history.state,"phase")=="finished"))return out;
            if(GetTickCount64()>=end) {out.response.put("status",V::string("accepted_running"));out.exit_code=5;return out;}
            Sleep(25);
        }
    }catch(const Failure& error) {return unknown_watch(request,id,last,error.what(),error.platform);}
     catch(const std::exception& error) {return unknown_watch(request,id,last,error.what());}
}
ExportActions export_actions() {
    ExportActions ports;ports.prepare=[](const V& p) {
        auto policy=V::object();for(const auto n:{"identifiers","raw_values","interpretations","customer_data"}) {
            const auto selected=p.find(std::string("include_")+n);policy.put(n,V::boolean_value(selected && selected->kind==V::Kind::boolean && selected->boolean));
        }
        return prepare_report_worker(text(p,"case_operation_id"),text(p,"case_directory"),policy,text(p,"destination"),text(p,"state_directory"));
    };ports.execute=start_report_worker;return ports;
}
Outcome dispatch_report_operation(const std::string& request,const std::string& command,const V& parameters) {
    if(command=="operation.watch")return watch_report_worker(request,parameters);
    if(command!="operation.inspect" && command!="operation.cancel.request")return refused(request,"command_unavailable",3);
    if(!operation_parameters(parameters,false))return refused(request,"invalid_parameter");
    return export_observation(request,observe_report_worker(text(parameters,"operation_id"),text(parameters,"state_directory"),command=="operation.cancel.request",true));
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
        Recorder recorder{records.value,h,r::History{}};recorder.save(state,"report_prepared");
        ReportResult result{r::joined_definition(field(h,"definition"))?e::VerificationCaseExportOutcome{}.view():e::AcquisitionExportOutcome{}.view(),V{}};
        std::unique_ptr<ReportSession> session;bool dispatched=false;
        try {
            session=reconstruct(field(h,"definition"));delay(L"DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY");
            if(!SetEvent(event.value))fail("report_worker_admission_signal");event=Handle();delay(L"DISKED_REPORT_WORKER_TEST_EFFECT_DELAY");
            state.put("phase",V::string("executing")).put("effect_certainty",V::string("in_flight"));recorder.save(state,"report_executing");dispatched=true;
            const auto stop=[&] {
                const auto flag=read_file(cancel.value,1);if(flag!="0" && flag!="1")reject("report_worker_cancel_invalid");
                if(flag=="1" && text(state,"cancellation_observation")=="not_observed") {state.put("cancellation_observation",V::string("observed"));recorder.save(state,"report_cancel_observed");}
                return flag=="1";
            };
            result=session->execute(stop);
        }catch(const std::exception& error) {
            result.outcome.put("diagnostic",V::string(error.what()));auto output=field(result.outcome,"output");output.put("diagnostic",V::string(error.what()));
            if(dispatched) {result.outcome.put("status",V::string("unknown"));output.put("status",V::string("failed")).put("output_state",V::string("uncertain"))
                .put("uncertain_effect",V::boolean_value(true)).put("written_bytes",V{});}result.outcome.put("output",output);
        }
        session.reset(); // Handles are released before recording effect quiescence.
        delay(L"DISKED_REPORT_WORKER_TEST_RECEIPT_DELAY");state.put("phase",V::string("finished")).put("quiescent",V::boolean_value(true))
            .put("effect_certainty",V::string(field(field(result.outcome,"output"),"uncertain_effect").boolean?"uncertain":"observed")).put("outcome",result.outcome).put("receipt",result.receipt);
        recorder.save(state,"report_finished");if(event.valid())SetEvent(event.value);return 0;
    }catch(...) {return 199;}
}
}
