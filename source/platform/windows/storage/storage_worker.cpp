#include "storage_worker.h"
#include <set>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("storage_worker_shape");return *p;}
std::uint64_t integer(const V& x){if(x.kind!=V::Kind::string || !json::decimal_u64(x.text))throw std::invalid_argument("storage_worker_integer");return std::stoull(x.text);}
V number(std::uint64_t n){return V::string(std::to_string(n));}
V policy_value(const StorageQueryPolicy& p){return V::object().put("descriptor_bytes",number(p.descriptor_bytes)).put("string_bytes",number(p.string_bytes)).put("extents",number(p.extents));}
StorageInput request(const V& v){
    StorageInput r;r.capture_epoch=integer(get(v,"capture_epoch"));r.provider_input=get(v,"provider_input");const auto& p=get(v,"policy");if(p.kind!=V::Kind::object || p.fields.size()!=3)throw std::invalid_argument("storage_worker_policy");
    const auto d=integer(get(p,"descriptor_bytes")),s=integer(get(p,"string_bytes")),e=integer(get(p,"extents"));if(d<40 || d>4096 || !s || s>256 || !e || e>64)throw std::invalid_argument("storage_worker_policy");
    r.policy.descriptor_bytes=static_cast<DWORD>(d);r.policy.string_bytes=static_cast<DWORD>(s);r.policy.extents=static_cast<DWORD>(e);validate_storage_input(r);return r;
}
ObservationWorkerProfile profile(){
    ObservationWorkerProfile p;p.prefix="storage";p.scope="injected-storage-metadata";p.input_schema="org.disked.nt-storage-worker-input/1";p.reply_schema="org.disked.nt-storage-worker-reply/1";
    p.observation_schema="org.disked.nt-storage-worker-observation/1";p.role=L"__disked_nt_storage_fixture_worker";p.attempt_prefix="storage-attempt:";p.records_field="resources";
    p.input_mapping_bytes=278528;p.input_limits=storage_worker_limits();p.input_limits.bytes=278524;p.provider_limits=p.input_limits;p.provider_limits.bytes=262144;p.provider_limits.values=32768;p.reply_limits=storage_worker_limits();
    p.validate_request=[](const V& v){request(v);};p.validate_result=[](const V& value,const V& h){const auto r=request(h);read_storage_frame(value,get(h,"provider_input"),r.capture_epoch,r.policy);};return p;
}
}
json::Limits storage_worker_limits(){json::Limits l;l.bytes=786432;l.values=40000;l.depth=24;return l;}
void validate_storage_input(const StorageInput& r){
    if(!r.capture_epoch || r.provider_input.kind!=V::Kind::object || r.policy.descriptor_bytes<40 || r.policy.descriptor_bytes>4096 || !r.policy.string_bytes || r.policy.string_bytes>256 || !r.policy.extents || r.policy.extents>64)throw std::invalid_argument("storage_worker_request");
    auto l=storage_worker_limits();l.bytes=262144;l.values=32768;json::dump(r.provider_input,l);storage_fixture_subjects(r.provider_input);
}
std::unique_ptr<StorageWorker> StorageWorker::prepare(const StorageInput& r){
    validate_storage_input(r);auto v=V::object().put("capture_epoch",number(r.capture_epoch)).put("policy",policy_value(r.policy)).put("provider_input",r.provider_input);
    return std::unique_ptr<StorageWorker>(new StorageWorker(ObservationWorker::prepare(v,profile())));
}
int storage_worker_role(int argc,wchar_t** argv,const StorageFactory& factory){
    return observation_worker_role(argc,argv,profile(),[&](const V& h,const std::function<void()>& notify)->ObservationCollector{
        const auto r=request(h);const auto api=factory(get(h,"provider_input"),notify);const auto subjects=storage_fixture_subjects(get(h,"provider_input"));
        for(const auto& s:subjects){StorageQueryPort check(api,s.handle,r.policy);}
        return [r,api,subjects](const std::function<bool()>& stop){return collect_storage_frame(api,subjects,r.capture_epoch,r.policy,stop)->value();};
    });
}
}}
