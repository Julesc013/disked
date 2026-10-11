#include "storage_identity.h"
#include <algorithm>
#include <map>
#include <set>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k){const auto* p=v.find(k);if(!p)throw std::invalid_argument("storage_identity_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("storage_identity_shape");return p.text;}
std::uint64_t number(const V& v,const char* k){const auto s=text(v,k);if(!json::decimal_u64(s))throw std::invalid_argument("storage_identity_integer");return std::stoull(s);}
bool flag(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::boolean)throw std::invalid_argument("storage_identity_shape");return p.boolean;}
std::string encoded(const V& v){return json::dump(v,storage_identity_limits());}
std::string hash(const V& v){return digest_sha256(encoded(v));}
bool nonzero(const std::string& s){return !s.empty() && s.find_first_not_of('0')!=s.npos;}
V select(const V& v,std::initializer_list<const char*> keys){auto out=V::object();for(const auto k:keys)out.put(k,get(v,k));return out;}
V sorted(V v){if(v.kind!=V::Kind::array)throw std::invalid_argument("storage_identity_shape");std::sort(v.items.begin(),v.items.end(),[](const V& a,const V& b){return encoded(a)<encoded(b);});return v;}
V name(const V& v){return select(v,{"state","original_hex","ascii_conformant"});}
V normalized(const V& v,const std::string& component){
    if(component=="descriptor"){
        auto out=select(v,{"device_type","device_type_modifier","removable_raw","queueing_raw","bus_type","raw_properties_bytes","raw_properties_sha256"});
        for(const auto k:{"vendor","product","revision","serial"})out.put(k,name(get(v,k)));return out;
    }
    if(component=="identifiers"){
        auto out=V::array();for(const auto& id:get(v,"identifiers").items)out.items.push_back(select(id,{"code_set","type","association","original_hex","interpretation"}));return sorted(std::move(out));
    }
    if(component=="alignment")return select(v,{"logical_sector_bytes","physical_sector_bytes","sector_alignment_offset_bytes","cache_line_bytes","cache_alignment_offset_bytes"});
    if(component=="layout"){
        auto out=V::object().put("partition_style",get(v,"partition_style"));
        if(text(v,"partition_style")=="0")out.put("mbr_signature_raw",get(v,"mbr_signature_raw"));
        if(text(v,"partition_style")=="1")for(const auto k:{"gpt_disk_guid_hex","usable_start_bytes","usable_length_bytes","max_partition_count"})out.put(k,get(v,k));
        auto parts=V::array();for(const auto& p:get(v,"partitions").items){
            if(!flag(p,"active"))continue;auto n=select(p,{"offset_bytes","length_bytes","end_bytes"});
            if(text(v,"partition_style")=="0")n.put("mbr_type",get(p,"mbr_type")).put("boot_flag_raw",get(p,"boot_flag_raw"));
            else n.put("gpt_type_guid_hex",get(p,"gpt_type_guid_hex")).put("gpt_partition_guid_hex",get(p,"gpt_partition_guid_hex")).put("gpt_attributes",get(p,"gpt_attributes")).put("gpt_name_hex",get(get(p,"gpt_name"),"original_hex"));
            parts.items.push_back(std::move(n));
        }
        return out.put("partitions",sorted(std::move(parts)));
    }
    if(component=="extents"){
        auto out=V::array();for(const auto& x:v.items)out.items.push_back(select(x,{"disk_number","offset_bytes","length_bytes","end_bytes"}));return sorted(std::move(out));
    }
    return v;
}
struct Group {std::string kind,key;V occurrences=V::array();};
void candidate(std::map<std::string,Group>& groups,const std::string& kind,const std::string& key,const V& subject,const V& ordinal){
    const auto token=kind+":"+key;auto& group=groups[token];group.kind=kind;group.key=key;
    group.occurrences.items.push_back(V::object().put("subject",subject).put("ordinal",ordinal));
}
V claims(){return V::object().put("owned_process_binding_verified",V::boolean_value(true)).put("physical_identity",V::string("unknown"))
    .put("physical_association",V::string("unproven")).put("current_resource_freshness",V::string("unknown")).put("capture_consistency",V::string("sequential-not-atomic"))
    .put("complete_alias_proof",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false)).put("atomic_snapshot",V::boolean_value(false));}
const V& subject(const V& v,const std::string& key){for(const auto& row:get(v,"resources").items)if(text(row,"subject")==key)return row;throw std::invalid_argument("storage_identity_subject");}
}
json::Limits storage_identity_limits(){json::Limits l;l.bytes=786432;l.values=40000;l.depth=24;return l;}
std::string storage_identity_digest(const StorageIdentityObservation& v){return hash(v.value());}
std::shared_ptr<const StorageIdentityObservation> observe_storage_identity(const StorageFrameSnapshot& owned,const IdentityBinding& expected){
    const auto& frame=owned.frame();const auto& key=owned.key();const auto frame_digest=digest_sha256(json::dump(frame.value(),storage_observation_limits())),context_digest=digest_sha256(json::dump(owned.context()));
    if(frame.profile()!=StorageFrameProfile::IdentityLayout || text(owned.context(),"storage_profile")!="identity-layout")throw std::invalid_argument("storage_identity_profile");
    if(!key.domain)throw std::invalid_argument("storage_identity_domain");
    if(!(key==expected.capture) || expected.frame_digest!=frame_digest || expected.context_digest!=context_digest)throw std::invalid_argument("storage_identity_binding");
    auto binding=V::object().put("domain",V::string("capture-domain-local:"+std::to_string(key.domain->local_ordinal()))).put("source",V::string(key.source)).put("capture",V::string(std::to_string(key.capture))).put("worker",V::string(std::to_string(key.worker))).put("frame_digest",V::string(frame_digest)).put("context_digest",V::string(context_digest));
    auto rows=V::array();std::map<std::string,Group> groups;std::map<std::string,bool> critical,missing;
    for(const auto& resource:get(frame.value(),"resources").items){
        const auto& components=get(resource,"components");const auto& conflicts=get(resource,"conflicts");const auto key_text=text(resource,"key");auto states=V::object(),facts=V::object(),hints=V::object().put("label",get(resource,"label"));bool usable_id=false,conformant=true;
        for(const auto& entry:components.fields){
            states.put(entry.first,get(entry.second,"state"));if(text(entry.second,"state")!="observed")continue;const auto& value=get(entry.second,"data");
            if(entry.first=="number"){hints.put("number",value);continue;}facts.put(entry.first,normalized(value,entry.first));
            if(entry.first=="descriptor")for(const auto k:{"vendor","product","revision","serial"})conformant=conformant && flag(get(value,k),"ascii_conformant");
            if(entry.first=="descriptor"){
                const auto& serial=get(value,"serial");if(text(serial,"state")=="present" && flag(serial,"ascii_conformant") && !text(serial,"original_hex").empty())candidate(groups,"serial",text(serial,"original_hex"),get(resource,"key"),V{});
            }
            if(entry.first=="identifiers")for(const auto& id:get(value,"identifiers").items){
                const bool useful=text(id,"interpretation")=="reported" && text(id,"association")=="0" && nonzero(text(id,"original_hex"));usable_id=usable_id || useful;
                if(useful)candidate(groups,"device-identifier",text(id,"comparison_key"),get(resource,"key"),get(id,"ordinal"));
            }
            if(entry.first=="layout"){
                if(text(value,"partition_style")=="0" && text(value,"mbr_signature_raw")!="0")candidate(groups,"mbr-signature",text(value,"mbr_signature_raw"),get(resource,"key"),V{});
                if(text(value,"partition_style")=="1"){
                    if(nonzero(text(value,"gpt_disk_guid_hex")))candidate(groups,"gpt-disk-guid",text(value,"gpt_disk_guid_hex"),get(resource,"key"),V{});
                    for(const auto& p:get(value,"partitions").items)if(flag(p,"active") && nonzero(text(p,"gpt_partition_guid_hex")))candidate(groups,"gpt-partition-guid",text(p,"gpt_partition_guid_hex"),get(resource,"key"),get(p,"ordinal"));
                }
            }
        }
        if(text(resource,"kind")=="disk" && hints.find("number")){const auto& n=get(hints,"number");if(text(n,"device_type")=="7" && text(n,"partition_raw")=="0")candidate(groups,"disk-number-hint",text(n,"device_number"),get(resource,"key"),V{});}
        bool bad=false;for(const auto k:{"capacity_disagreement","alignment_disagreement","partition_range_disagreement","reported_layout_conflict"})bad=bad || flag(conflicts,k);
        bool absent=text(resource,"kind")!="disk" || !usable_id || !conformant;
        for(const auto k:{"descriptor","geometry","length","identifiers","alignment","layout"})absent=absent || text(states,k)!="observed";
        critical[key_text]=bad;missing[key_text]=absent;
        auto payload=V::object().put("binding",binding).put("subject",get(resource,"key")).put("kind",get(resource,"kind"));
        rows.items.push_back(V::object().put("subject",get(resource,"key")).put("kind",get(resource,"kind")).put("observation_id",V::string("identity-observation:"+hash(payload).substr(7)))
            .put("lookup_hints",hints).put("component_states",states).put("facts",facts).put("reported_fingerprint",V::string(hash(facts))).put("reported_conflicts",conflicts)
            .put("not_observed",V::array()).put("usable_device_identifier",V::boolean_value(usable_id)));
        for(const auto k:{"controller_path","lun","namespace","exclusive_ownership","media_generation"})rows.items.back().fields["not_observed"].items.push_back(V::string(k));
    }
    auto collisions=V::array();std::set<std::string> ambiguous;
    for(auto& pair:groups){auto& g=pair.second;if(g.occurrences.items.size()<2)continue;g.occurrences=sorted(std::move(g.occurrences));
        for(const auto& x:g.occurrences.items)ambiguous.insert(text(x,"subject"));
        collisions.items.push_back(V::object().put("kind",V::string(g.kind)).put("key",V::string(g.key)).put("occurrences",g.occurrences)
            .put("relationship",V::string(g.kind=="disk-number-hint"?"duplicate-lookup-hint":"possible-alias-or-clone")));
    }
    for(auto& row:rows.items){const auto k=text(row,"subject");row.put("quality",V::string(critical[k]?"conflicting":ambiguous.count(k)?"ambiguous":missing[k]?"insufficient":"complete_selected_reports"));}
    std::sort(rows.items.begin(),rows.items.end(),[](const V& a,const V& b){return text(a,"subject")<text(b,"subject");});
    auto out=V::object().put("schema",V::string("org.disked.nt-composite-identity-prototype/1")).put("binding",binding).put("worker_context",owned.context()).put("frame_status",get(frame.value(),"status"))
        .put("resources",std::move(rows)).put("collisions",collisions).put("claims",claims());json::dump(out,storage_identity_limits());
    return std::shared_ptr<const StorageIdentityObservation>(new StorageIdentityObservation(std::move(out),key.domain));
}
V compare_storage_identity(const StorageIdentityObservation& previous,const StorageIdentityObservation& current,const IdentityComparisonBinding& expected){
    if(expected.previous_digest!=storage_identity_digest(previous) || expected.current_digest!=storage_identity_digest(current))throw std::invalid_argument("storage_identity_comparison_binding");
    if(!previous.epoch_domain() || previous.epoch_domain()!=current.epoch_domain())throw std::invalid_argument("storage_identity_comparison_domain");
    const auto& a=previous.value();const auto& b=current.value();const auto& ka=get(a,"binding");const auto& kb=get(b,"binding");
    if(text(ka,"source")!=text(kb,"source") || number(kb,"capture")<number(ka,"capture") || number(kb,"worker")<=number(ka,"worker"))throw std::invalid_argument("storage_identity_comparison_epoch");
    const auto& ra=subject(a,expected.previous_subject);const auto& rb=subject(b,expected.current_subject);
    if(text(ra,"kind")!="disk" || text(rb,"kind")!="disk")throw std::invalid_argument("storage_identity_comparison_subject");
    const auto& fa=get(ra,"facts");const auto& fb=get(rb,"facts");std::set<std::string> keys;for(const auto& x:fa.fields)keys.insert(x.first);for(const auto& x:fb.fields)keys.insert(x.first);auto changes=V::array();
    for(const auto& k:keys){const auto pa=fa.find(k),pb=fb.find(k);if((!pa || !pb) || encoded(*pa)!=encoded(*pb))changes.items.push_back(V::object().put("component",V::string(k)).put("previous",pa?*pa:V{}).put("current",pb?*pb:V{}));}
    const auto relation=changes.items.empty()?"unchanged-reported-evidence":"changed-reported-evidence";
    auto out=V::object().put("schema",V::string("org.disked.nt-identity-comparison-prototype/1")).put("previous_digest",V::string(expected.previous_digest)).put("current_digest",V::string(expected.current_digest))
        .put("previous_subject",V::string(expected.previous_subject)).put("current_subject",V::string(expected.current_subject))
        .put("relation",V::string(text(ra,"quality")=="complete_selected_reports" && text(rb,"quality")=="complete_selected_reports"?relation:"incomparable")).put("reported_relation",V::string(relation))
        .put("changes",changes).put("previous_quality",get(ra,"quality")).put("current_quality",get(rb,"quality")).put("continuity",V::string("caller-declared-subject-lookup; physical association unproven")).put("claims",claims());
    json::dump(out,storage_identity_limits());return out;
}
}}
