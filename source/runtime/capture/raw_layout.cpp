#include "raw_layout.h"
#include "mbr.h"
#include "ebr.h"
#include "gpt.h"
#include "sha256.h"
#include <algorithm>

namespace disked {
namespace {
using V=json::Value;
void check(int code) {if(code!=DE_OK)throw RawLayoutError("raw_layout_internal");}
std::string decimal(const de_u64& n) {char b[21];check(de_u64_format(&n,b,sizeof(b)));return b;}
V exact(const de_u64& n) {return V::string(decimal(n));}
V number(std::size_t n) {return V::string(std::to_string(n));}
std::string hex(const unsigned char* p,std::size_t n) {
    const char* d="0123456789abcdef";std::string out;out.reserve(n*2);
    for(std::size_t i=0;i<n;++i) {out+=d[p[i]>>4];out+=d[p[i]&15];}return out;
}
std::string hash(const de_view& v) {unsigned char d[32];sha256(v.data,v.size,d);return "sha256:"+hex(d,32);}
class Prefix {
    const std::vector<unsigned char>& bytes_;
    const de_block_space& space_;
public:
    Prefix(const std::vector<unsigned char>& bytes,const de_block_space& space):bytes_(bytes),space_(space) {}
    de_view region(const de_block_extent& e) const {
        de_byte_extent b{};check(de_extent_to_bytes(&e,&b));de_u64 size{};check(de_u64_from_size(bytes_.size(),&size));
        if(de_u64_compare(&b.start,&size)>=0)return {nullptr,0};
        const auto end=de_u64_compare(&b.end,&size)>0?size:b.end;de_u64 length{};
        check(de_u64_sub(&end,&b.start,&length));std::size_t at=0,n=0;
        check(de_u64_to_size(&b.start,&at));check(de_u64_to_size(&length,&n));return {bytes_.data()+at,n};
    }
    de_view block(const de_u64& lba) const {
        de_block_extent e{};const auto one=de_u64_from_u32(1);
        if(de_extent_make(&space_,&lba,&one,&e)!=DE_OK)return {nullptr,0};return region(e);
    }
};
V extent(const de_block_extent& e) {
    de_byte_extent b{};check(de_extent_to_bytes(&e,&b));de_u64 length{};check(de_u64_sub(&b.end,&b.start,&length));
    return V::object().put("offset_bytes",exact(b.start)).put("length_bytes",exact(length)).put("end_bytes",exact(b.end));
}
V mbr_record(const de_mbr_entry& e,const char* role,unsigned slot,const de_u64& table_lba) {
    auto row=e.range_valid?extent(e.extent):V::object();
    return row.put("role",V::string(role)).put("slot",number(slot)).put("table_lba",exact(table_lba))
        .put("range_valid",V::boolean_value(e.range_valid!=0)).put("issues",number(e.issues))
        .put("mbr_type",number(e.raw[4])).put("boot",V::boolean_value(e.raw[0]==0x80))
        .put("relative_start",exact(e.relative_start)).put("original_digest",V::string(hash({e.raw,16})));
}
V gpt_record(const de_gpt_entry& e,unsigned slot) {
    auto row=e.range_valid?extent(e.extent):V::object();
    return row.put("role",V::string("gpt-partition")).put("slot",number(slot))
        .put("range_valid",V::boolean_value(e.range_valid!=0)).put("issues",number(e.issues))
        .put("gpt_type_guid_hex",V::string(hex(e.raw.data,16))).put("gpt_partition_guid_hex",V::string(hex(e.raw.data+16,16)))
        .put("gpt_attributes",exact(e.attributes)).put("gpt_name_hex",V::string(hex(e.raw.data+56,72)))
        .put("original_digest",V::string(hash(e.raw)));
}
}
json::Limits raw_layout_limits() {json::Limits l;l.bytes=131072;l.depth=16;l.values=16384;l.string_bytes=512;return l;}
std::shared_ptr<const RawPartitionLayout> decode_raw_layout(const std::vector<unsigned char>& bytes,const de_u64& blocks,de_u32 unit,RawLayoutPolicy policy) {
    if(unit!=512 && unit!=4096)throw RawLayoutError("raw_layout_geometry");
    if(!policy.partitions || policy.partitions>64 || !policy.ebr_nodes || policy.ebr_nodes>DE_EBR_LIMIT)throw RawLayoutError("raw_layout_policy");
    if(bytes.size()>16U*1024U*1024U)throw RawLayoutError("raw_layout_input_budget");
    const auto zero=de_u64_from_u32(0),one=de_u64_from_u32(1),scale=de_u64_from_u32(unit);de_u64 capacity{},captured{};
    if(!de_u64_compare(&blocks,&zero) || de_u64_mul(&blocks,&scale,&capacity))throw RawLayoutError("raw_layout_capacity");
    check(de_u64_from_size(bytes.size(),&captured));if(de_u64_compare(&captured,&capacity)>0)throw RawLayoutError("raw_layout_geometry");
    de_block_space space{};check(de_space_init("raw-layout",10,&blocks,unit,&space));Prefix prefix(bytes,space);
    auto out=V::object().put("schema",V::string("org.disked.raw-layout-observation-prototype/1"))
        .put("geometry",V::object().put("blocks",exact(blocks)).put("logical_sector_bytes",number(unit)).put("capacity_bytes",exact(capacity)))
        .put("source",V::object().put("captured_bytes",exact(captured)).put("declared_bytes",exact(capacity))
            .put("sha256",V::string(hash({bytes.data(),bytes.size()}))).put("complete",V::boolean_value(de_u64_compare(&captured,&capacity)==0))
            .put("consistency",V::string("unknown")))
        .put("policy",V::object().put("partitions",number(policy.partitions)).put("ebr_nodes",number(policy.ebr_nodes)))
        .put("chs_geometry",V::string("unknown; CHS correspondence not compared"));
    const auto first=prefix.block(zero);de_mbr_geometry chs{};de_mbr_table mbr{};
    const auto mbr_status=de_mbr_read(&first,&space,&chs,&mbr);
    auto mbr_info=V::object().put("status",number(mbr_status)).put("issues",number(mbr.issues)).put("signature",V::boolean_value(mbr.signature!=0));
    if(first.size>=444) {de_u64 signature{};check(de_view_read_uint(&first,440,4,DE_LITTLE_ENDIAN,&signature));mbr_info.put("disk_signature",exact(signature));}
    out.put("mbr",mbr_info);
    de_gpt_header headers[2]{};de_gpt_candidate candidates[2]{};std::vector<de_gpt_entry> workspace[2];
    const de_gpt_limits limits{1024,4096,1048576};auto copies=V::array();bool gpt_seen=false,gpt_budget=false;
    for(unsigned i=0;i<2;++i) {
        auto lba=one;int status=DE_OK;if(i)status=de_u64_sub(&blocks,&one,&lba);
        auto copy=V::object().put("role",V::string(i?"backup":"primary"));
        if(status==DE_OK) {const auto view=prefix.block(lba);status=de_gpt_header_read(&view,&space,&lba,i?DE_GPT_BACKUP:DE_GPT_PRIMARY,&headers[i]);}
        copy.put("status",number(status)).put("header_issues",number(headers[i].issues));
        if(status==DE_OK) {
            candidates[i].header=&headers[i];
            if(!(headers[i].issues&(DE_GPT_SIGNATURE|DE_GPT_TRUNCATED)))gpt_seen=true;
            copy.put("header_consistent",V::boolean_value(headers[i].consistent!=0)).put("count",number(headers[i].count))
                .put("entry_bytes",number(headers[i].entry_size));de_block_extent request{};
            const auto requested=de_gpt_request_array(&headers[i],&limits,&request);copy.put("request_status",number(requested));
            if(requested==DE_BUFFER)gpt_budget=true;
            if(requested==DE_OK) {
                workspace[i].resize(headers[i].count);const auto view=prefix.region(request);
                const auto read=de_gpt_array_read(&headers[i],&limits,&view,workspace[i].data(),workspace[i].size(),&candidates[i]);
                copy.put("array_status",number(read));
                if(read==DE_OK) {
                    std::size_t active=0;for(const auto& e:workspace[i])if(e.active)++active;
                    copy.put("array_issues",number(candidates[i].issues)).put("array_complete",V::boolean_value(candidates[i].complete!=0))
                        .put("array_consistent",V::boolean_value(candidates[i].consistent!=0)).put("active_count",number(active))
                        .put("array_digest",V::string(hash(candidates[i].raw_array)));
                }
            }
        }
        copies.items.push_back(std::move(copy));
    }
    out.put("copies",copies);int relation=DE_GPT_INCOMPARABLE;
    const auto compared=de_gpt_compare(&candidates[0],&candidates[1],&relation);
    out.put("copy_relation",number(compared==DE_OK?relation:DE_GPT_INCOMPARABLE));
    bool protective=false;for(const auto& e:mbr.entries)if(e.raw[4]==0xee)protective=true;
    std::string style="unrecognized",state="unrecognized";auto entries=V::array(),links=V::array(),walks=V::array();
    if(gpt_seen || protective) {
        style=(mbr.issues&DE_MBR_HYBRID)?"ambiguous":"gpt";state=gpt_budget?"budget_exhausted":"incomparable";
        if(style=="gpt" && mbr.signature && protective && !mbr.issues && compared==DE_OK && relation==DE_GPT_AGREE) {
            const auto& h=headers[0];de_block_extent usable{};check(de_extent_from_inclusive(&space,&h.first_usable,&h.last_usable,&usable));
            auto disk=extent(usable);disk.put("gpt_disk_guid_hex",V::string(hex(h.disk_guid,16))).put("partition_slots",number(h.count));out.put("disk",std::move(disk));
            for(std::size_t i=0;i<workspace[0].size();++i)if(workspace[0][i].active)entries.items.push_back(gpt_record(workspace[0][i],static_cast<unsigned>(i+1)));
            state=entries.items.size()>policy.partitions?"budget_exhausted":"complete";
        }
    } else if(mbr_status==DE_OK && mbr.signature) {
        style="mbr";state=mbr.issues?"incomparable":"complete";
        for(unsigned slot=0;slot<4;++slot) {
            const auto& root=mbr.entries[slot];if(!root.active)continue;
            entries.items.push_back(mbr_record(root,root.kind==DE_MBR_EXTENDED?"extended-container":"primary-partition",slot+1,zero));
            if(root.kind!=DE_MBR_EXTENDED || !root.range_valid)continue;
            std::vector<de_ebr_node> nodes(policy.ebr_nodes);de_ebr_walk walk{};
            check(de_ebr_init(&mbr,slot,&chs,nodes.data(),nodes.size(),policy.ebr_nodes,&walk));
            while(walk.needs_block) {const auto pending=walk.pending;const auto view=prefix.block(pending);check(view.size?de_ebr_feed(&walk,&pending,&view):de_ebr_unavailable(&walk));}
            walks.items.push_back(V::object().put("slot",number(slot+1)).put("count",number(walk.count))
                .put("complete",V::boolean_value(walk.complete!=0)).put("issues",number(walk.issues)));
            if(!walk.complete || walk.issues)state=(walk.issues&DE_MBR_BUDGET)?"budget_exhausted":"incomparable";
            for(std::size_t i=0;i<walk.count;++i) {
                const auto& table=nodes[i].table;if(table.entries[0].active)entries.items.push_back(mbr_record(table.entries[0],"logical-partition",1,nodes[i].lba));
                if(table.entries[1].active)links.items.push_back(mbr_record(table.entries[1],"ebr-link",2,nodes[i].lba));
            }
        }
        if(entries.items.size()>policy.partitions || links.items.size()>128)state="budget_exhausted";
        out.put("disk",V::object().put("mbr_signature_raw",*mbr_info.find("disk_signature")));
    } else if(mbr.issues&DE_MBR_TRUNCATED)state="incomplete";
    out.put("active_count",number(entries.items.size())).put("structural_count",number(links.items.size()));
    if(state!="complete") {entries=V::array();links=V::array();}
    out.put("style",V::string(style)).put("state",V::string(state)).put("entries",std::move(entries)).put("links",std::move(links)).put("walks",std::move(walks))
        .put("claims",V::object().put("physical_identity",V::string("unknown")).put("physical_association",V::string("unproven"))
            .put("mutation_authority",V::boolean_value(false)).put("metadata_complete",V::boolean_value(state=="complete")));
    try {json::dump(out,raw_layout_limits());}catch(const json::Error&) {throw RawLayoutError("raw_layout_output_budget");}
    return std::shared_ptr<const RawPartitionLayout>(new RawPartitionLayout(std::move(out)));
}
}
