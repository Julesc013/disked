#include "namespace_worker.h"
#include "observation_worker.h"
#include "worker_files.h"
#include <cstddef>
#include <cstring>
#include <set>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;using namespace worker_files;
constexpr std::size_t reply_bytes=393216;
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

}
json::Limits namespace_worker_limits() {json::Limits l;l.bytes=reply_bytes;l.values=20000;l.depth=24;return l;}
void validate_namespace_input(const NamespaceInput& input) {valid(input);}
void validate_namespace_snapshot(const V& snapshot,std::uint64_t capture,const InventoryPolicy& policy) {
    NamespaceInput input;input.capture_epoch=capture;input.policy=policy;input.provider_input=V::object();valid(input);
    if(text(snapshot,"schema")!="org.disked.nt-volume-namespace-prototype/1" || text(snapshot,"capture_epoch")!=std::to_string(capture) ||
        text(snapshot,"api_binding")!="injected-win32-table" || text(snapshot,"scope")!="volume-namespace-only" ||
        json::dump(field(snapshot,"policy"))!=json::dump(policy_value(policy)))throw std::invalid_argument("namespace_snapshot_binding");
    const auto binding=V::object().put("capture_epoch",number(capture)).put("policy",policy_value(policy));snapshot_shape(snapshot,binding);
    const auto& claims=field(snapshot,"claims");
    if(text(claims,"physical_identity")!="unknown" || text(claims,"full_topology")!="not_observed" || text(claims,"media_preservation")!="not_established")throw std::invalid_argument("namespace_snapshot_claims");
    for(const auto key:{"physical_admission","mutation_authority","complete_alias_proof"})if(field(claims,key).kind!=V::Kind::boolean || field(claims,key).boolean)throw std::invalid_argument("namespace_snapshot_claims");
    std::size_t units=0;
    for(const auto& row:field(snapshot,"records").items) {
        const auto& mounts=field(row,"mounts");
        if(text(mounts,"state")=="observed") {
            ++units;for(const auto& name:field(mounts,"paths").items)units+=text(name,"original_hex").size()/4+1;
        }
    }
    if(units>policy.mount_units)throw std::invalid_argument("namespace_snapshot_units");
    json::dump(snapshot,volume_inventory_limits());
}
namespace {
ObservationWorkerProfile profile() {
    ObservationWorkerProfile p;p.prefix="namespace";p.scope="injected-volume-namespace";p.input_schema="org.disked.nt-namespace-worker-input/1";
    p.reply_schema="org.disked.nt-namespace-worker-reply/1";p.observation_schema="org.disked.nt-namespace-worker-observation/1";
    p.role=L"__disked_nt_namespace_fixture_worker";p.attempt_prefix="namespace-attempt:";p.records_field="records";
    p.input_mapping_bytes=98304;p.input_limits=namespace_worker_limits();p.input_limits.bytes=98300;p.input_limits.values=18000;
    p.provider_limits=p.input_limits;p.provider_limits.bytes=65535;p.provider_limits.values=16384;p.reply_limits=namespace_worker_limits();
    p.validate_request=[](const V& v){request(v);};
    p.validate_result=[](const V& snapshot,const V& h){const auto r=request(h);validate_namespace_snapshot(snapshot,r.capture_epoch,r.policy);};return p;
}
}
struct NamespaceWorker::Impl {std::unique_ptr<ObservationWorker> worker;};
NamespaceWorker::NamespaceWorker(std::unique_ptr<Impl> p):impl_(std::move(p)){}
NamespaceWorker::~NamespaceWorker()=default;
std::unique_ptr<NamespaceWorker> NamespaceWorker::prepare(const NamespaceInput& r){
    valid(r);auto v=V::object().put("capture_epoch",number(r.capture_epoch)).put("policy",policy_value(r.policy)).put("provider_input",r.provider_input);
    std::unique_ptr<Impl> p(new Impl());p->worker=ObservationWorker::prepare(v,profile());return std::unique_ptr<NamespaceWorker>(new NamespaceWorker(std::move(p)));
}
std::unique_ptr<NamespaceWorker> NamespaceWorker::start(const NamespaceInput& r){auto p=prepare(r);p->launch();return p;}
void NamespaceWorker::launch(){impl_->worker->launch();}
bool NamespaceWorker::never_launched() const{return impl_->worker->never_launched();}
void NamespaceWorker::release(){impl_->worker->release();}
void NamespaceWorker::cancel(){impl_->worker->cancel();}
bool NamespaceWorker::wait_entered(DWORD ms){return impl_->worker->wait_entered(ms);}
V NamespaceWorker::observe(DWORD ms){return impl_->worker->observe(ms);}
V NamespaceWorker::retire(DWORD ms){return impl_->worker->retire(ms);}
int namespace_worker_role(int argc,wchar_t** argv,const VolumeFactory& factory){
    return observation_worker_role(argc,argv,profile(),[&](const V& h,const std::function<void()>& notify)->ObservationCollector{
        const auto r=request(h);auto api=factory(field(h,"provider_input"),notify);const auto native=native_volume_api();
        if(api.first==native.first || api.next==native.next || api.close==native.close || api.mounts==native.mounts || api.error==native.error)throw std::invalid_argument("namespace_native_port_not_admitted");
        auto cursor=std::make_shared<VolumeCursor>(api);return [cursor,r](const std::function<bool()>& cancelled){return collect_volume_namespace(*cursor,r.capture_epoch,r.policy,cancelled);};
    });
}
}}
