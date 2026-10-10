#include "storage_worker.h"
#include <set>
namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k){const auto p=v.find(k);if(!p)throw std::invalid_argument("storage_worker_shape");return *p;}
std::uint64_t integer(const V& x){if(x.kind!=V::Kind::string || !json::decimal_u64(x.text))throw std::invalid_argument("storage_worker_integer");return std::stoull(x.text);}
V number(std::uint64_t n){return V::string(std::to_string(n));}
V policy_value(const StorageInput& r){auto v=V::object().put("descriptor_bytes",number(r.policy.descriptor_bytes)).put("string_bytes",number(r.policy.string_bytes)).put("extents",number(r.policy.extents));
    if(r.profile==StorageFrameProfile::IdentityLayout)v.put("identifiers",number(r.policy.identifiers)).put("partitions",number(r.policy.partitions));return v;}
StorageInput request(const V& v,StorageFrameProfile selected){
    StorageInput r;r.profile=selected;r.capture_epoch=integer(get(v,"capture_epoch"));r.provider_input=get(v,"provider_input");const auto& p=get(v,"policy");if(p.kind!=V::Kind::object || p.fields.size()!=(selected==StorageFrameProfile::IdentityLayout?5U:3U))throw std::invalid_argument("storage_worker_policy");
    const auto d=integer(get(p,"descriptor_bytes")),s=integer(get(p,"string_bytes")),e=integer(get(p,"extents"));if(d<40 || d>4096 || !s || s>256 || !e || e>64)throw std::invalid_argument("storage_worker_policy");
    r.policy.descriptor_bytes=static_cast<DWORD>(d);r.policy.string_bytes=static_cast<DWORD>(s);r.policy.extents=static_cast<DWORD>(e);
    if(selected==StorageFrameProfile::IdentityLayout){const auto ids=integer(get(p,"identifiers")),parts=integer(get(p,"partitions"));if(!ids || ids>32 || !parts || parts>64)throw std::invalid_argument("storage_worker_policy");r.policy.identifiers=static_cast<DWORD>(ids);r.policy.partitions=static_cast<DWORD>(parts);}
    validate_storage_input(r);return r;
}
ObservationWorkerProfile profile(StorageFrameProfile selected){
    ObservationWorkerProfile p;p.prefix="storage";p.scope="injected-storage-metadata";p.input_schema="org.disked.nt-storage-worker-input/1";p.reply_schema="org.disked.nt-storage-worker-reply/1";
    p.observation_schema="org.disked.nt-storage-worker-observation/1";p.role=L"__disked_nt_storage_fixture_worker";p.attempt_prefix="storage-attempt:";p.records_field="resources";
    if(selected==StorageFrameProfile::IdentityLayout){p.prefix="identity";p.scope="injected-storage-identity-layout";p.input_schema="org.disked.nt-storage-worker-input/2";p.reply_schema="org.disked.nt-storage-worker-reply/2";
        p.observation_schema="org.disked.nt-storage-worker-observation/2";p.role=L"__disked_nt_identity_fixture_worker";p.attempt_prefix="identity-attempt:";}
    p.input_mapping_bytes=278528;p.input_limits=storage_worker_limits();p.input_limits.bytes=278524;p.provider_limits=p.input_limits;p.provider_limits.bytes=262144;p.provider_limits.values=32768;p.reply_limits=storage_worker_limits();
    p.validate_request=[selected](const V& v){request(v,selected);};p.validate_result=[selected](const V& value,const V& h){const auto r=request(h,selected);read_storage_frame(value,get(h,"provider_input"),r.capture_epoch,r.policy,selected);};return p;
}
}
json::Limits storage_worker_limits(){json::Limits l;l.bytes=786432;l.values=40000;l.depth=24;return l;}
void validate_storage_input(const StorageInput& r){
    if(!r.capture_epoch || r.provider_input.kind!=V::Kind::object || r.policy.descriptor_bytes<40 || r.policy.descriptor_bytes>4096 || !r.policy.string_bytes || r.policy.string_bytes>256 || !r.policy.extents || r.policy.extents>64)throw std::invalid_argument("storage_worker_request");
    if(r.profile!=StorageFrameProfile::Metadata && r.profile!=StorageFrameProfile::IdentityLayout)throw std::invalid_argument("storage_worker_profile");
    if(!r.policy.identifiers || r.policy.identifiers>32 || !r.policy.partitions || r.policy.partitions>64)throw std::invalid_argument("storage_worker_policy");
    const auto tag=r.provider_input.find("profile");
    if(r.profile==StorageFrameProfile::IdentityLayout){if(!tag || tag->kind!=V::Kind::string || tag->text!="identity-layout")throw std::invalid_argument("storage_worker_profile");}
    else if(r.policy.identifiers!=32 || r.policy.partitions!=64 || (tag && tag->text=="identity-layout"))throw std::invalid_argument("storage_worker_profile");
    auto l=storage_worker_limits();l.bytes=262144;l.values=32768;json::dump(r.provider_input,l);storage_fixture_subjects(r.provider_input);
}
std::unique_ptr<StorageWorker> StorageWorker::prepare(const StorageInput& r){
    validate_storage_input(r);auto v=V::object().put("capture_epoch",number(r.capture_epoch)).put("policy",policy_value(r)).put("provider_input",r.provider_input);
    return std::unique_ptr<StorageWorker>(new StorageWorker(ObservationWorker::prepare(v,profile(r.profile))));
}
int storage_worker_role(int argc,wchar_t** argv,const StorageFactory& factory,StorageFrameProfile selected){
    return observation_worker_role(argc,argv,profile(selected),[&](const V& h,const std::function<void()>& notify)->ObservationCollector{
        const auto r=request(h,selected);const auto api=factory(get(h,"provider_input"),notify);const auto subjects=storage_fixture_subjects(get(h,"provider_input"));
        for(const auto& s:subjects){StorageQueryPort check(api,s.handle,r.policy);}
        return [r,api,subjects](const std::function<bool()>& stop){return collect_storage_frame(api,subjects,r.capture_epoch,r.policy,stop,r.profile)->value();};
    });
}
}}
