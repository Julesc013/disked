#include "namespace_worker.h"
#include "worker_files.h"
#include <cstddef>
#include <cstring>
#include <set>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;using namespace worker_files;
constexpr std::size_t input_bytes=98304,reply_bytes=393216;
struct Input {DWORD length;char bytes[input_bytes-sizeof(DWORD)];};
struct Output {volatile LONG ready,entered;DWORD length;char digest[64];char bytes[reply_bytes];};
static_assert(sizeof(Input)==input_bytes,"fixed input layout");
static_assert(offsetof(Output,bytes)==76,"fixed reply layout");
struct View {
    void* value=nullptr;
    View(HANDLE file,DWORD access,std::size_t bytes) {value=MapViewOfFile(file,access,0,0,bytes);if(!value)fail("namespace_mapping_unavailable");}
    ~View() {if(value)UnmapViewOfFile(value);}
    View(const View&)=delete;View& operator=(const View&)=delete;
};
json::Limits input_limits() {auto l=namespace_worker_limits();l.bytes=sizeof(Input::bytes);l.values=18000;return l;}
std::uint64_t integer(const V& x) {if(x.kind!=V::Kind::string || !json::decimal_u64(x.text))throw std::invalid_argument("namespace_integer");return std::stoull(x.text);}
const V& field(const V& x,const char* n) {const auto p=x.find(n);if(!p)throw std::invalid_argument("namespace_shape");return *p;}
void exact(const V& v,const std::set<std::string>& keys) {if(v.kind!=V::Kind::object || v.fields.size()!=keys.size())throw std::invalid_argument("namespace_shape");for(const auto& x:v.fields)if(!keys.count(x.first))throw std::invalid_argument("namespace_shape");}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
V policy_value(const InventoryPolicy& p) {return V::object().put("volumes",number(p.volumes)).put("mounts",number(p.mounts)).put("mount_units",number(p.mount_units)).put("include_mounts",V::boolean_value(p.include_mounts));}
void valid(const NamespaceInput& r) {
    if(!r.capture_epoch || !r.policy.volumes || r.policy.volumes>64 || !r.policy.mounts || r.policy.mounts>64 || !r.policy.mount_units || r.policy.mount_units>8192 || r.provider_input.kind!=V::Kind::object)throw std::invalid_argument("namespace_request");
    json::Limits l;l.bytes=65535;l.values=16384;l.depth=24;json::dump(r.provider_input,l);
}
NamespaceInput request(const V& h) {
    NamespaceInput r;r.capture_epoch=integer(field(h,"capture_epoch"));const auto& p=field(h,"policy");exact(p,{"volumes","mounts","mount_units","include_mounts"});
    const auto v=integer(field(p,"volumes")),m=integer(field(p,"mounts")),u=integer(field(p,"mount_units"));
    if(v>64 || m>64 || u>8192 || field(p,"include_mounts").kind!=V::Kind::boolean)throw std::invalid_argument("namespace_policy");
    r.policy.volumes=static_cast<std::uint32_t>(v);r.policy.mounts=static_cast<std::uint32_t>(m);r.policy.mount_units=static_cast<std::uint32_t>(u);r.policy.include_mounts=field(p,"include_mounts").boolean;
    r.provider_input=field(h,"provider_input");valid(r);return r;
}
void header(const V& h) {
    exact(h,{"schema","scope","host_id","code_sha256","capture_epoch","observer_epoch","worker_epoch","attempt_id","policy","provider_input"});
    if(text(h,"schema")!="org.disked.nt-namespace-worker-input/1" || text(h,"scope")!="injected-volume-namespace")throw std::invalid_argument("namespace_scope");
    for(const auto key:{"host_id","code_sha256","observer_epoch","worker_epoch","attempt_id"})if(text(h,key).empty())throw std::invalid_argument("namespace_binding");request(h);
}
void snapshot_shape(const V& s,const V& h) {
    exact(s,{"schema","provider","capture_epoch","status","scope","api_binding","policy","enumeration","close","records","claims"});
    if(text(s,"provider")!="windows.volume-namespace.prototype" || !std::set<std::string>{"complete","partial","cancelled","denied","unavailable"}.count(text(s,"status")))throw std::invalid_argument("namespace_snapshot_shape");
    const auto& enumeration=field(s,"enumeration");exact(enumeration,{"state","platform_code","exhausted"});
    if(!std::set<std::string>{"exhausted","denied","unavailable","malformed","adapter_exception","cancelled","budget_exhausted"}.count(text(enumeration,"state")))throw std::invalid_argument("namespace_snapshot_shape");
    if(integer(field(enumeration,"platform_code"))>0xffffffffULL || field(enumeration,"exhausted").kind!=V::Kind::boolean || field(enumeration,"exhausted").boolean!=(text(enumeration,"state")=="exhausted"))throw std::invalid_argument("namespace_snapshot_shape");
    const auto& close=field(s,"close");exact(close,{"state","platform_code"});
    if(!std::set<std::string>{"not_open","closed","uncertain"}.count(text(close,"state")) || integer(field(close,"platform_code"))>0xffffffffULL || (text(s,"status")=="complete" && (!field(enumeration,"exhausted").boolean || text(close,"state")=="uncertain")))throw std::invalid_argument("namespace_snapshot_shape");
    auto name=[](const V& value,bool mount) {
        exact(value,{"original_encoding","original_hex","display_encoding","display"});const auto hex=text(value,"original_hex");
        if(hex.size()%4 || hex.size()>(mount?1024U:252U) || (mount && hex.empty()))throw std::invalid_argument("namespace_snapshot_name");
        auto nibble=[](char c)->unsigned {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);throw std::invalid_argument("namespace_snapshot_name");};
        std::wstring original;for(std::size_t at=0;at<hex.size();at+=4)original+=static_cast<wchar_t>((nibble(hex[at])<<4)|nibble(hex[at+1])|(nibble(hex[at+2])<<12)|(nibble(hex[at+3])<<8));
        if(json::dump(value)!=json::dump(lossless_name(original)))throw std::invalid_argument("namespace_snapshot_name");
    };
    const auto& rows=field(s,"records");const auto& policy=field(h,"policy");if(rows.kind!=V::Kind::array || rows.items.size()>integer(field(policy,"volumes")))throw std::invalid_argument("namespace_snapshot_shape");
    if((text(s,"status")=="cancelled" && text(enumeration,"state")!="cancelled") || ((text(s,"status")=="denied" || text(s,"status")=="unavailable") && (!rows.items.empty() || text(enumeration,"state")!=text(s,"status"))))throw std::invalid_argument("namespace_snapshot_shape");
    std::size_t mounts=0;
    for(std::size_t at=0;at<rows.items.size();++at) {
        const auto& row=rows.items[at];exact(row,{"observation_id","volume_path","state","conflicts","mounts"});name(field(row,"volume_path"),false);
        if(text(row,"observation_id")!="nt-volume-observation:"+text(h,"capture_epoch")+":"+std::to_string(at+1) || (text(row,"state")!="present" && text(row,"state")!="malformed"))throw std::invalid_argument("namespace_snapshot_shape");
        const auto& conflicts=field(row,"conflicts");exact(conflicts,{"duplicate_volume_name","duplicate_mount_alias"});
        for(const auto key:{"duplicate_volume_name","duplicate_mount_alias"})if(field(conflicts,key).kind!=V::Kind::boolean || (field(conflicts,key).boolean && text(s,"status")=="complete"))throw std::invalid_argument("namespace_snapshot_shape");
        const auto& paths=field(row,"mounts");exact(paths,{"state","platform_code","paths"});const auto& values=field(paths,"paths");
        if(!std::set<std::string>{"observed","not_selected","not_queried","cancelled","budget_exhausted","adapter_exception","denied","unavailable","malformed","changed"}.count(text(paths,"state")))throw std::invalid_argument("namespace_snapshot_shape");
        if(text(s,"status")=="complete" && (text(row,"state")!="present" || text(paths,"state")!=(field(policy,"include_mounts").boolean?"observed":"not_selected")))throw std::invalid_argument("namespace_snapshot_shape");
        if(integer(field(paths,"platform_code"))>0xffffffffULL || values.kind!=V::Kind::array || values.items.size()>32 || (text(paths,"state")!="observed" && !values.items.empty()))throw std::invalid_argument("namespace_snapshot_shape");
        for(const auto& value:values.items)name(value,true);mounts+=values.items.size();
    }
    if(mounts>integer(field(policy,"mounts")))throw std::invalid_argument("namespace_snapshot_shape");
    exact(field(s,"claims"),{"physical_identity","full_topology","media_preservation","physical_admission","mutation_authority","complete_alias_proof"});
}
Handle section(const Security& s,std::size_t size) {auto a=s.attributes;Handle h(CreateFileMappingW(INVALID_HANDLE_VALUE,&a,PAGE_READWRITE,0,static_cast<DWORD>(size),nullptr));if(!h.valid())fail("namespace_mapping_create");return h;}
Handle event(const Security& s) {auto a=s.attributes;Handle h(CreateEventW(&a,TRUE,FALSE,nullptr));if(!h.valid())fail("namespace_event_create");return h;}
void signal(HANDLE h) {if(!SetEvent(h))fail("namespace_event_signal");}
V permissions() {return V::object().put("live_namespace",V::boolean_value(false)).put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false)).put("durable_reconnect",V::boolean_value(false));}
}
json::Limits namespace_worker_limits() {json::Limits l;l.bytes=reply_bytes;l.values=20000;l.depth=24;return l;}
struct NamespaceWorker::Impl {
    Security security;Image image;Directory code_parent;WorkerBudget aggregate;
    Handle input,output,cancellation,admission,gate,job,process;std::unique_ptr<View> view;
    V binding;std::string input_digest,created,last_bytes;DWORD pid=0;bool cancellation_requested=false,retired=false;
    Impl():code_parent(narrow(image.path.substr(0,image.path.find_last_of(L'\\')))),aggregate(security,true) {}
};
NamespaceWorker::NamespaceWorker(std::unique_ptr<Impl> p):impl_(std::move(p)) {}
NamespaceWorker::~NamespaceWorker()=default;
std::unique_ptr<NamespaceWorker> NamespaceWorker::start(const NamespaceInput& r) {
    valid(r);std::unique_ptr<Impl> p(new Impl());
    p->binding=V::object().put("schema",V::string("org.disked.nt-namespace-worker-input/1")).put("scope",V::string("injected-volume-namespace"))
        .put("host_id",V::string(p->security.host_id)).put("code_sha256",V::string(p->image.digest)).put("capture_epoch",number(r.capture_epoch))
        .put("observer_epoch",V::string(p->security.identity("observer:"))).put("worker_epoch",V::string(p->security.identity("worker:")))
        .put("attempt_id",V::string(p->security.identity("namespace-attempt:"))).put("policy",policy_value(r.policy)).put("provider_input",r.provider_input);
    const auto bytes=json::dump(p->binding,input_limits());p->input_digest=hash(bytes);
    p->input=section(p->security,sizeof(Input));p->output=section(p->security,sizeof(Output));
    {View v(p->input.value,FILE_MAP_WRITE,sizeof(Input));auto target=static_cast<Input*>(v.value);target->length=static_cast<DWORD>(bytes.size());std::memcpy(target->bytes,bytes.data(),bytes.size());}
    p->view.reset(new View(p->output.value,FILE_MAP_READ,sizeof(Output)));
    p->cancellation=event(p->security);p->admission=event(p->security);p->gate=event(p->security);
    auto a=p->security.attributes;p->job=Handle(CreateJobObjectW(&a,nullptr));if(!p->job.valid())fail("namespace_job_create");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY|JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=128*1024*1024;
    if(!SetInformationJobObject(p->job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))fail("namespace_job_limits");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION observed{};
    if(!QueryInformationJobObject(p->job.value,JobObjectExtendedLimitInformation,&observed,sizeof(observed),nullptr) || observed.BasicLimitInformation.LimitFlags!=limits.BasicLimitInformation.LimitFlags || observed.BasicLimitInformation.ActiveProcessLimit!=1 || observed.ProcessMemoryLimit!=128*1024*1024)fail("namespace_job_limits_mismatch");
    auto ci=inherited(p->input.value,FILE_MAP_READ),co=inherited(p->output.value,FILE_MAP_WRITE),cc=inherited(p->cancellation.value,SYNCHRONIZE),ca=inherited(p->admission.value,EVENT_MODIFY_STATE),cg=inherited(p->gate.value,SYNCHRONIZE);
    std::vector<HANDLE> handles={ci.value,co.value,cc.value,ca.value,cg.value},jobs={p->aggregate.job.value,p->job.value};AttributeList attributes(handles,jobs);
    STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.lpAttributeList=attributes.list;
    startup.StartupInfo.hStdInput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdOutput=INVALID_HANDLE_VALUE;startup.StartupInfo.hStdError=INVALID_HANDLE_VALUE;
    std::wstring command=L"\""+p->image.path+L"\" __disked_nt_namespace_fixture_worker";for(const auto h:handles)command+=L" "+std::to_wstring(reinterpret_cast<std::uintptr_t>(h));
    p->code_parent.check();PROCESS_INFORMATION raw{};
    if(!CreateProcessW(p->image.path.c_str(),&command[0],nullptr,nullptr,TRUE,DETACHED_PROCESS|EXTENDED_STARTUPINFO_PRESENT,nullptr,p->code_parent.path.c_str(),&startup.StartupInfo,&raw))fail("namespace_spawn_failed");
    p->process=Handle(raw.hProcess);Handle thread(raw.hThread);p->pid=raw.dwProcessId;p->created=process_created(p->process.value);
    return std::unique_ptr<NamespaceWorker>(new NamespaceWorker(std::move(p)));
}
void NamespaceWorker::release() {signal(impl_->gate.value);}
void NamespaceWorker::cancel() {signal(impl_->cancellation.value);impl_->cancellation_requested=true;}
bool NamespaceWorker::wait_entered(DWORD ms) {
    if(ms>1000)throw std::invalid_argument("namespace_wait_budget");const auto end=GetTickCount64()+ms;
    for(;;) {MemoryBarrier();if(static_cast<const Output*>(impl_->view->value)->entered)return true;
        if(WaitForSingleObject(impl_->process.value,0)!=WAIT_TIMEOUT || GetTickCount64()>=end)return false;Sleep(1);}
}
V NamespaceWorker::observe(DWORD ms) {
    if(ms>1000)throw std::invalid_argument("namespace_wait_budget");auto& p=*impl_;const auto wait=WaitForSingleObject(p.process.value,ms);
    const std::string state=wait==WAIT_OBJECT_0?"exited":wait==WAIT_TIMEOUT?"running":"unavailable";DWORD exit=STILL_ACTIVE;if(!GetExitCodeProcess(p.process.value,&exit))exit=STILL_ACTIVE;
    auto out=V::object().put("schema",V::string("org.disked.nt-namespace-worker-observation/1")).put("status",V::string(state=="running"?"accepted_running":"unknown"))
        .put("attempt_id",field(p.binding,"attempt_id")).put("capture_epoch",field(p.binding,"capture_epoch")).put("observer_epoch",field(p.binding,"observer_epoch"))
        .put("worker_epoch",field(p.binding,"worker_epoch")).put("request_digest",V::string(p.input_digest)).put("code_sha256",field(p.binding,"code_sha256"))
        .put("worker",V::object().put("pid",number(p.pid)).put("created",V::string(p.created)).put("observation",V::string(state)).put("exit_code",number(exit)))
        .put("admitted",V::boolean_value(WaitForSingleObject(p.admission.value,0)==WAIT_OBJECT_0)).put("cancellation_requested",V::boolean_value(p.cancellation_requested))
        .put("retired",V::boolean_value(p.retired)).put("result",V{}).put("diagnostic",V{}).put("claims",permissions());
    try {
        const auto* value=static_cast<const Output*>(p.view->value);MemoryBarrier();const auto ready=value->ready;MemoryBarrier();
        if(!ready)return out;if(ready!=1 || !value->length || value->length>reply_bytes)throw std::invalid_argument("namespace_publication");
        const std::string bytes(value->bytes,value->length),digest(value->digest,64);MemoryBarrier();
        if(value->ready!=ready || value->length!=bytes.size() || hash(bytes)!=digest)throw std::invalid_argument("namespace_publication_digest");
        if(!p.last_bytes.empty() && p.last_bytes!=bytes)throw std::invalid_argument("namespace_reply_changed");
        const auto reply=json::parse(bytes,namespace_worker_limits());exact(reply,{"schema","scope","host_id","code_sha256","capture_epoch","observer_epoch","worker_epoch","attempt_id","request_digest","pid","created","snapshot"});
        if(text(reply,"schema")!="org.disked.nt-namespace-worker-reply/1" || text(reply,"scope")!="injected-volume-namespace" || text(reply,"request_digest")!=p.input_digest || integer(field(reply,"pid"))!=p.pid || text(reply,"created")!=p.created)throw std::invalid_argument("namespace_reply_binding");
        for(const auto key:{"host_id","code_sha256","capture_epoch","observer_epoch","worker_epoch","attempt_id"})if(text(reply,key)!=text(p.binding,key))throw std::invalid_argument("namespace_reply_binding");
        const auto& snapshot=field(reply,"snapshot");if(text(snapshot,"schema")!="org.disked.nt-volume-namespace-prototype/1" || text(snapshot,"capture_epoch")!=text(p.binding,"capture_epoch") || text(snapshot,"api_binding")!="injected-win32-table" || text(snapshot,"scope")!="volume-namespace-only" || json::dump(field(snapshot,"policy"))!=json::dump(field(p.binding,"policy")))throw std::invalid_argument("namespace_snapshot_binding");
        snapshot_shape(snapshot,p.binding);
        const auto& claims=field(snapshot,"claims");if(text(claims,"physical_identity")!="unknown" || text(claims,"full_topology")!="not_observed" || text(claims,"media_preservation")!="not_established")throw std::invalid_argument("namespace_snapshot_claims");
        for(const auto key:{"physical_admission","mutation_authority","complete_alias_proof"})if(field(claims,key).kind!=V::Kind::boolean || field(claims,key).boolean)throw std::invalid_argument("namespace_snapshot_claims");
        json::dump(snapshot,volume_inventory_limits());p.last_bytes=bytes;out.put("status",V::string("completed")).put("result",snapshot);
    }catch(const std::exception& error) {out.put("status",V::string("unknown")).put("diagnostic",V::string(error.what()));if(!p.last_bytes.empty())out.put("last_validated_result",field(json::parse(p.last_bytes,namespace_worker_limits()),"snapshot"));}
    return out;
}
V NamespaceWorker::retire(DWORD ms) {
    if(ms>2000)throw std::invalid_argument("namespace_retirement_budget");auto& p=*impl_;
    if(WaitForSingleObject(p.process.value,0)==WAIT_TIMEOUT) {if(!TerminateJobObject(p.job.value,31))fail("namespace_retirement_unresolved");p.retired=true;}
    WaitForSingleObject(p.process.value,ms);return observe();
}
int namespace_worker_role(int argc,wchar_t** argv,const VolumeFactory& factory) {
    if(argc!=7)return 2;
    try {
        auto hi=Handle(argument_handle(argv[2])),ho=Handle(argument_handle(argv[3])),hc=Handle(argument_handle(argv[4])),ha=Handle(argument_handle(argv[5])),hg=Handle(argument_handle(argv[6]));
        Security security;WorkerBudget budget(security,false);Image image;View input(hi.value,FILE_MAP_READ,sizeof(Input)),output(ho.value,FILE_MAP_WRITE,sizeof(Output));
        const auto* raw=static_cast<const Input*>(input.value);if(!raw->length || raw->length>sizeof(raw->bytes))throw std::invalid_argument("namespace_input_size");
        const std::string bytes(raw->bytes,raw->length);const auto h=json::parse(bytes,input_limits());header(h);
        if(text(h,"host_id")!=security.host_id || text(h,"code_sha256")!=image.digest)throw std::invalid_argument("namespace_worker_code");
        const auto r=request(h);auto* value=static_cast<Output*>(output.value);auto api=factory(r.provider_input,[value] {InterlockedExchange(&value->entered,1);});VolumeCursor cursor(api);
        if(cursor.native_binding())throw std::invalid_argument("namespace_native_port_not_admitted");signal(ha.value);
        if(WaitForSingleObject(hg.value,1000)!=WAIT_OBJECT_0)return 4;
        const auto snapshot=collect_volume_namespace(cursor,r.capture_epoch,r.policy,[&] {return WaitForSingleObject(hc.value,0)==WAIT_OBJECT_0;});
        auto reply=h;reply.fields.erase("policy");reply.fields.erase("provider_input");reply.put("schema",V::string("org.disked.nt-namespace-worker-reply/1")).put("request_digest",V::string(hash(bytes)))
            .put("pid",number(GetCurrentProcessId())).put("created",V::string(process_created(GetCurrentProcess()))).put("snapshot",snapshot);
#ifdef DISKED_NT_NAMESPACE_WORKER_TESTING
        const auto fault=r.provider_input.find("reply_fault");const auto mode=fault&&fault->kind==V::Kind::string?fault->text:"";
        if(mode=="capture")reply.put("capture_epoch",V::string("0"));if(mode=="worker")reply.put("worker_epoch",V::string("stale-worker"));
        if(mode=="shape")reply.fields["snapshot"].put("records",V{});
        if(mode=="status")reply.fields["snapshot"].put("status",V::string("invented"));
        if(mode=="claims")reply.fields["snapshot"].fields["claims"].put("physical_admission",V::boolean_value(true));
        if(mode=="schema")reply.put("schema",V::string("unknown-producer"));
#endif
        const auto serialized=json::dump(reply,namespace_worker_limits()),digest=hash(serialized);value->length=static_cast<DWORD>(serialized.size());
        std::memcpy(value->bytes,serialized.data(),serialized.size());std::memcpy(value->digest,digest.data(),digest.size());MemoryBarrier();InterlockedExchange(&value->ready,1);
#ifdef DISKED_NT_NAMESPACE_WORKER_TESTING
        if(mode=="digest")value->digest[0]=value->digest[0]=='0'?'1':'0';
        if(mode=="hold")Sleep(500);
#endif
        return 0;
    }catch(const std::exception&) {return 3;}
}
}}
