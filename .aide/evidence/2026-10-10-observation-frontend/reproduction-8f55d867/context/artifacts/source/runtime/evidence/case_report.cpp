#include "case_report.h"
#include "sha256.h"
#include <algorithm>

namespace disked { namespace evidence { namespace proposal {
using V=json::Value;
namespace {
const V& get(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw Error("case_shape");return *p;}
void shape(const V& v,std::initializer_list<const char*> keys) {
    if(v.kind!=V::Kind::object || v.fields.size()!=keys.size())throw Error("case_shape");for(const auto key:keys)get(v,key);
}
void digest_value(const V& v) {
    if(v.kind!=V::Kind::string || v.text.size()!=71 || v.text.substr(0,7)!="sha256:" || v.text.find_first_not_of("0123456789abcdef",7)!=v.text.npos)throw Error("case_digest");
}
std::string hash(const V& v) {
    std::string bytes;try {bytes=json::dump(v,case_limits());}catch(const json::Error&) {throw Error("case_byte_limit");}
    unsigned char out[32];sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),out);
    const char* hex="0123456789abcdef";std::string text="sha256:";for(const auto b:out) {text+=hex[b>>4];text+=hex[b&15];}return text;
}
V claims() {
    return V::object().put("authenticity",V::string("not_established")).put("physical_admission",V::boolean_value(false))
        .put("source_preservation",V::string("not_established")).put("storage_postconditions",V::string("not_established"))
        .put("reliability",V::string("not_established")).put("mutation_authority",V::boolean_value(false));
}
unsigned policy_number(const V& v) {
    shape(v,{"identifiers","raw_values","interpretations","customer_data"});unsigned mask=0,bit=1;
    for(const auto name:{"identifiers","raw_values","interpretations","customer_data"}) {
        const auto& b=get(v,name);if(b.kind!=V::Kind::boolean)throw Error("case_policy");if(b.boolean)mask|=bit;bit<<=1;
    }return mask;
}
V policy_value(unsigned mask) {
    V p=V::object();unsigned bit=1;for(const auto name:{"identifiers","raw_values","interpretations","customer_data"}) {p.put(name,V::boolean_value((mask&bit)!=0));bit<<=1;}return p;
}
// Only requested public observations participate. Never compare/hint at omitted
// customer, identifier or secret values. Declaration matching is not admission.
V public_fields(const V& capture,bool& comparable,V& bindings) {
    V sources=V::object();std::size_t count=0;
    for(const auto& source:get(capture,"sources").items) {
        V values=V::object(),names=V::array();
        for(const auto& field:get(source,"fields").items)if(get(field,"sensitivity").text=="public") {
            ++count;const auto& raw=get(field,"raw");const auto& interpreted=get(field,"interpretation");
            if(!get(field,"received").boolean || get(raw,"availability").text!="available" || get(interpreted,"availability").text!="available")comparable=false;
            values.put(get(field,"id").text,V::object().put("raw",raw).put("interpretation",interpreted));
            names.items.push_back(get(field,"id"));
        }
        // Bind the observer even if it has no public fields; a replaced observer
        // is not treated as comparable solely because values look the same.
        sources.put(get(source,"id").text,V::object().put("provider_digest",get(source,"provider_digest")).put("fields",values));
        std::sort(names.items.begin(),names.items.end(),[](const V& a,const V& b) {return a.text<b.text;});
        bindings.put(get(source,"id").text,V::object().put("provider_digest",get(source,"provider_digest")).put("public_fields",names));
    }
    if(!count)comparable=false;return sources;
}
V comparison(const V* before,const V* after) {
    std::string state="not_comparable";
    if(before && after) {
        bool comparable=true;V first_bindings=V::object(),last_bindings=V::object();
        const auto first=public_fields(*before,comparable,first_bindings),last=public_fields(*after,comparable,last_bindings);
        if(json::dump(get(*before,"target"))!=json::dump(get(*after,"target")))comparable=false;
        if(json::dump(first_bindings,case_limits())!=json::dump(last_bindings,case_limits()))comparable=false;
        if(comparable)state=json::dump(first,case_limits())==json::dump(last,case_limits())?"equal":"different";
    }
    return V::object().put("kind",V::string("inference")).put("basis",V::string("requested_public_observations"))
        .put("state",V::string(state)).put("scope",V::string("recorded_fixture_values"))
        .put("fresh_sampling_established",V::boolean_value(false)).put("authorizes_execution",V::boolean_value(false));
}
void bounded(const V& value) {
    try {json::dump(value,case_limits());}catch(const json::Error&) {throw Error("case_byte_limit");}
}
}
json::Limits case_limits() {json::Limits l;l.bytes=1048576;l.string_bytes=8192;l.values=131072;l.depth=32;return l;}
Case::Case(const std::string& id,const V& code):id_(id),code_(code) {
    if(id.empty() || id.size()>128 || id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_.@-")!=id.npos)throw Error("case_id");
    shape(code,{"source_revision","input_digest","configuration_digest"});
    const auto& revision=get(code,"source_revision");
    if(revision.kind!=V::Kind::string || revision.text.size()!=40 || revision.text.find_first_not_of("0123456789abcdef")!=revision.text.npos)throw Error("case_code_revision");
    digest_value(get(code,"input_digest"));digest_value(get(code,"configuration_digest"));
    context_=hash(V::object().put("case_id",V::string(id_)).put("code_identity",code_));
}
V Case::full(const std::vector<Entry>& entries,bool closed) const {
    V records=V::array();const V* before=nullptr;const V* after=nullptr;
    for(const auto& entry:entries) {
        records.items.push_back(entry.record);const auto phase=get(entry.record,"phase").text;
        if(phase=="before")before=&get(entry.record,"capture");if(phase=="after")after=&get(entry.record,"capture");
    }
    return V::object().put("schema",V::string("org.disked.case-evidence-prototype/1")).put("case_id",V::string(id_))
        .put("code_identity",code_).put("context_digest",V::string(context_)).put("collection_state",V::string(closed?"closed":"open"))
        .put("records",records).put("comparison",comparison(before,after)).put("claims",claims());
}
void Case::append(const std::string& phase,const std::string& origin,const std::string& fixture,const health::proposal::Capture& capture) {
    if(closed_)throw Error("case_closed");if(entries_.size()>=16)throw Error("case_record_limit");
    if((entries_.empty() && phase!="before") || (!entries_.empty() && phase!="observation" && phase!="after"))throw Error("case_phase_order");
    if(origin!="compiled-fixture" && origin!="injected-fixture")throw Error("case_origin_unavailable");digest_value(V::string(fixture));
    Entry entry;entry.record=V::object().put("sequence",V::string(std::to_string(entries_.size()+1))).put("phase",V::string(phase))
        .put("event",V::string("observation_snapshot_recorded")).put("origin",V::string(origin)).put("fixture_digest",V::string(fixture))
        .put("context_digest",V::string(context_)).put("clock",V::object().put("domain",V::string("unobserved")).put("observed_at",V{}))
        .put("capture",capture.view()).put("previous_digest",entries_.empty()?V::string("sha256:"+std::string(64,'0')):get(entries_.back().record,"digest"));
    entry.record.put("digest",V::string(hash(entry.record)));
    // Keep a const deep snapshot, not an alias to a live collector. Copying its
    // worker declaration supplies no observer port or retirement authority.
    entry.snapshot=std::make_shared<const health::proposal::Capture>(capture);
    auto next=entries_;next.push_back(std::move(entry));const bool closed=phase=="after";bounded(full(next,closed));
    // Every policy is admissible only when its complete projection also fits.
    // The aggregate bound includes records/digests and cannot silently truncate.
    for(unsigned i=0;i<16;++i)bounded(project(next,closed,policy_value(i)));
    entries_.swap(next);closed_=closed;
}
V Case::view() const {auto v=full(entries_,closed_);bounded(v);return v;}
std::string Case::digest() const {return hash(view());}
V Case::project(const std::vector<Entry>& entries,bool closed,const V& policy) const {
    const auto mask=policy_number(policy);V records=V::array();std::string previous="sha256:"+std::string(64,'0');
    const V* before=nullptr;const V* after=nullptr;
    for(const auto& entry:entries) {
        const auto& phase=get(entry.record,"phase");V row=V::object().put("sequence",get(entry.record,"sequence")).put("phase",phase)
            .put("event",get(entry.record,"event")).put("origin",get(entry.record,"origin")).put("clock",get(entry.record,"clock"))
            .put("support_report",entry.snapshot->support(policy));
        // These digests cover only the disclosed projection. Never export the
        // private chain/context/fixture digest, even with all content flags.
        if(mask&1) {
            row.put("previous_projection_digest",V::string(previous));previous=hash(row);row.put("projection_digest",V::string(previous));
        }
        if(phase.text=="before")before=&get(entry.record,"capture");if(phase.text=="after")after=&get(entry.record,"capture");records.items.push_back(row);
    }
    auto v=V::object().put("schema",V::string("org.disked.case-support-prototype/1")).put("scope",V::string("fixture-observation-evidence"))
        .put("collection_state",V::string(closed?"closed":"open")).put("policy",policy).put("records",records)
        .put("custody_binding",V::string("selected-projection-only")).put("original_binding",V::string("omitted"))
        .put("claims",claims()).put("comparison",(mask&6)==6?comparison(before,after):V::object().put("state",V::string("not_disclosed")));
    if(mask&1)v.put("case_id",V::string(id_)).put("code_identity",code_);bounded(v);return v;
}
V Case::support(const V& policy) const {return project(entries_,closed_,policy);}
}}}
