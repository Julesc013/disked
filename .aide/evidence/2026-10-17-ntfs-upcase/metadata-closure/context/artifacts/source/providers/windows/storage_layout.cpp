#include "storage_layout.h"
#include <algorithm>
#include <set>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;
const V& get(const V& v,const char* k) {const auto* p=v.find(k);if(!p)throw std::invalid_argument("nt_layout_internal");return *p;}
std::string text(const V& v,const char* k) {return get(v,k).text;}
bool digest(const std::string& s) {return s.size()==71 && s.substr(0,7)=="sha256:" && std::all_of(s.begin()+7,s.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});}
const V* observed(const V& components,const char* name) {
    const auto* c=components.find(name);return c && text(*c,"state")=="observed"?&get(*c,"data"):nullptr;
}
bool same_extent(const V& a,const V& b) {
    return text(a,"offset_bytes")==text(b,"offset_bytes") && text(a,"length_bytes")==text(b,"length_bytes");
}
void different(V& differences,const char* scope,const std::string& field,const V& raw,const V& reported,const V& refs=V::object()) {
    if(json::dump(raw)==json::dump(reported))return;
    differences.items.push_back(V::object().put("scope",V::string(scope)).put("field",V::string(field))
        .put("raw",raw).put("reported",reported).put("records",refs));
}
}
json::Limits layout_comparison_limits() {json::Limits l;l.bytes=131072;l.depth=16;l.values=16384;l.string_bytes=512;return l;}
std::string raw_layout_digest(const RawPartitionLayout& raw) {return digest_sha256(json::dump(raw.value(),raw_layout_limits()));}
std::string storage_layout_frame_digest(const StorageFrame& frame) {return digest_sha256(json::dump(frame.value(),storage_observation_limits()));}
V compare_storage_layout(const StorageFrame& frame,const RawPartitionLayout& raw,const LayoutBinding& binding) {
    if(frame.profile()!=StorageFrameProfile::IdentityLayout)throw std::invalid_argument("nt_layout_profile");
    if(binding.subject.empty() || binding.subject.size()>128 || binding.capture.source.empty() || binding.capture.source.size()>128 || !binding.capture.capture || !binding.capture.worker ||
       text(frame.value(),"capture_epoch")!=std::to_string(binding.capture.capture) || !digest(binding.frame_digest) || !digest(binding.raw_digest) ||
       binding.frame_digest!=storage_layout_frame_digest(frame) || binding.raw_digest!=raw_layout_digest(raw))throw std::invalid_argument("nt_layout_binding");
    const V* subject=nullptr;for(const auto& r:get(frame.value(),"resources").items)if(text(r,"key")==binding.subject)subject=&r;
    if(!subject || text(*subject,"kind")!="disk")throw std::invalid_argument("nt_layout_subject");
    const auto& source=raw.value();const auto& geometry=get(source,"geometry");const auto& components=get(*subject,"components");
    auto matches=V::array(),structural=V::array(),differences=V::array(),missing=V::array(),extra=V::array(),ambiguities=V::array(),coverage=V::array();
    bool have_capacity=false,have_unit=false;const auto* native_geometry=observed(components,"geometry");
    const auto* native_length=observed(components,"length");const auto* alignment=observed(components,"alignment");
    if(native_geometry) {
        have_capacity=have_unit=true;
        different(differences,"geometry","geometry.capacity_bytes",get(geometry,"capacity_bytes"),get(*native_geometry,"disk_size_bytes"));
        different(differences,"geometry","geometry.logical_sector_bytes",get(geometry,"logical_sector_bytes"),get(*native_geometry,"logical_sector_bytes"));
    }
    if(native_length) {have_capacity=true;different(differences,"geometry","length.capacity_bytes",get(geometry,"capacity_bytes"),get(*native_length,"length_bytes"));}
    if(alignment) {have_unit=true;different(differences,"geometry","alignment.logical_sector_bytes",get(geometry,"logical_sector_bytes"),get(*alignment,"logical_sector_bytes"));}
    if(!have_capacity)coverage.items.push_back(V::string("native_capacity_unavailable"));
    if(!have_unit)coverage.items.push_back(V::string("native_logical_unit_unavailable"));
    const auto* layout=observed(components,"layout");const bool raw_complete=text(source,"state")=="complete";
    if(!raw_complete)coverage.items.push_back(V::string("raw_layout_"+text(source,"state")));
    if(!layout)coverage.items.push_back(V::string("native_layout_unavailable"));
    bool style_same=false;
    if(layout && raw_complete) {
        const auto style=text(*layout,"partition_style");const std::string expected=text(source,"style")=="mbr"?"0":"1";
        style_same=style==expected;
        different(differences,"disk","partition_style",V::string(expected),get(*layout,"partition_style"));
        if(style_same) {
            const auto& disk=get(source,"disk");
            if(expected=="0")different(differences,"disk","mbr_signature_raw",get(disk,"mbr_signature_raw"),get(*layout,"mbr_signature_raw"));
            else {
                different(differences,"disk","gpt_disk_guid_hex",get(disk,"gpt_disk_guid_hex"),get(*layout,"gpt_disk_guid_hex"));
                different(differences,"disk","usable_start_bytes",get(disk,"offset_bytes"),get(*layout,"usable_start_bytes"));
                different(differences,"disk","usable_length_bytes",get(disk,"length_bytes"),get(*layout,"usable_length_bytes"));
            }
            const auto& rows=get(source,"entries").items;const auto& links=get(source,"links").items;const auto& reported=get(*layout,"partitions").items;
            std::set<std::size_t> used;std::vector<const V*> active;
            for(const auto& r:reported)if(get(r,"active").boolean)active.push_back(&r);
            for(const auto& r:rows) {
                std::vector<std::size_t> candidates;
                for(std::size_t j=0;j<active.size();++j)if(same_extent(r,*active[j]))candidates.push_back(j);
                if(candidates.empty()) {missing.items.push_back(V::object().put("raw_slot",get(r,"slot")).put("role",get(r,"role")));continue;}
                if(candidates.size()!=1 || used.count(candidates[0])) {
                    ambiguities.items.push_back(V::object().put("raw_slot",get(r,"slot")).put("role",get(r,"role")).put("candidate_count",V::string(std::to_string(candidates.size()))));continue;
                }
                const auto j=candidates[0];used.insert(j);const auto& n=*active[j];
                auto refs=V::object().put("raw_slot",get(r,"slot")).put("raw_role",get(r,"role")).put("raw_table_lba",r.find("table_lba")?get(r,"table_lba"):V{})
                    .put("reported_ordinal",get(n,"ordinal"));const auto before=differences.items.size();
                if(expected=="0") {
                    different(differences,"partition","mbr_type",get(r,"mbr_type"),get(n,"mbr_type"),refs);
                    const auto boot=text(n,"boot_flag_raw");
                    if(boot!="0" && boot!="1")different(differences,"partition","mbr_boot_representation",V::string(get(r,"boot").boolean?"1":"0"),get(n,"boot_flag_raw"),refs);
                    else different(differences,"partition","boot",get(r,"boot"),V::boolean_value(boot=="1"),refs);
                } else {
                    for(const auto* field:{"gpt_type_guid_hex","gpt_partition_guid_hex","gpt_attributes"})different(differences,"partition",field,get(r,field),get(n,field),refs);
                    different(differences,"partition","gpt_name_hex",get(r,"gpt_name_hex"),get(get(n,"gpt_name"),"original_hex"),refs);
                }
                refs.put("state",V::string(before==differences.items.size()?"equal":"different"));matches.items.push_back(std::move(refs));
            }
            std::set<std::size_t> used_links;
            for(std::size_t j=0;j<active.size();++j)if(!used.count(j)) {
                const auto& n=*active[j];std::vector<std::size_t> candidates;
                if(expected=="0")for(std::size_t k=0;k<links.size();++k)if(same_extent(links[k],n) && text(links[k],"mbr_type")==text(n,"mbr_type"))candidates.push_back(k);
                if(candidates.size()==1 && used_links.insert(candidates[0]).second)structural.items.push_back(V::object().put("reported_ordinal",get(n,"ordinal")).put("raw_table_lba",get(links[candidates[0]],"table_lba")));
                else extra.items.push_back(V::object().put("reported_ordinal",get(n,"ordinal")).put("structural_candidates",V::string(std::to_string(candidates.size()))));
            }
        }
    }
    const bool contradiction=!differences.items.empty() || !missing.items.empty() || !extra.items.empty() || !ambiguities.items.empty();
    const char* state=!raw_complete || !layout || !have_capacity || !have_unit?"incomparable":contradiction?"disagree":"agree-within-scope";
    auto out=V::object().put("schema",V::string("org.disked.nt-raw-layout-comparison-prototype/1")).put("state",V::string(state))
        .put("binding",V::object().put("source",V::string(binding.capture.source)).put("capture_epoch",V::string(std::to_string(binding.capture.capture)))
            .put("worker_epoch",V::string(std::to_string(binding.capture.worker))).put("subject",V::string(binding.subject))
            .put("frame_digest",V::string(binding.frame_digest)).put("raw_digest",V::string(binding.raw_digest)).put("supplied_bytes_digest",get(get(source,"source"),"sha256")))
        .put("native_frame_status",get(frame.value(),"status")).put("raw_state",get(source,"state"))
        .put("matches",std::move(matches)).put("structural_matches",std::move(structural)).put("differences",std::move(differences))
        .put("missing",std::move(missing)).put("extra",std::move(extra)).put("ambiguities",std::move(ambiguities)).put("coverage",std::move(coverage))
        .put("scope",V::string("available-format-capacity-unit-disk-and-active-partition-fields; unique-extent-correlation; host-policy-fields-not-on-disk-equality"))
        .put("claims",V::object().put("binding_scope",V::string("fixture-declared-pairing")).put("physical_identity",V::string("unknown"))
            .put("physical_association",V::string("unproven")).put("owned_reader_authenticated",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false)));
    json::dump(out,layout_comparison_limits());return out;
}
}}
