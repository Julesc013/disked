#include "map_observation.h"
#include "mbr.h"
#include "ebr.h"
#include "gpt.h"
#include "sha256.h"
#include <algorithm>

namespace disked {
namespace {
using V=json::Value;
constexpr std::size_t input_limit=16U*1024U*1024U,detail_limit=8;
void require(int status) {if(status!=DE_OK)throw MapObservationError("image_observation_internal");}
V number(std::size_t n) {return V::number(std::to_string(n));}
std::string decimal(const de_u64& n) {char s[21];require(de_u64_format(&n,s,sizeof(s)));return s;}
V exact(const de_u64& n) {return V::string(decimal(n));}
std::string hex(const unsigned char* p,std::size_t n) {
    static const char digits[]="0123456789abcdef";std::string out;out.reserve(n*2);
    for(std::size_t i=0;i<n;++i) {out+=digits[p[i]>>4];out+=digits[p[i]&15];}return out;
}
std::string guid(const unsigned char* bytes) {
    char text[37];de_view v{bytes,16};require(de_gpt_guid_text(&v,text,sizeof(text)));return text;
}
class Prefix {
    const std::vector<unsigned char>& bytes_;
    const de_block_space& space_;
public:
    Prefix(const std::vector<unsigned char>& bytes,const de_block_space& space):bytes_(bytes),space_(space) {}
    de_view region(const de_block_extent& extent) const {
        de_byte_extent byte_extent{};require(de_extent_to_bytes(&extent,&byte_extent));
        std::size_t start=0,length=0;auto size=de_u64_from_u32(0);
        require(de_u64_from_size(bytes_.size(),&size));
        if(de_u64_compare(&byte_extent.start,&size)>=0)return {nullptr,0};
        require(de_u64_to_size(&byte_extent.start,&start));
        const auto end=de_u64_compare(&byte_extent.end,&size)>0?size:byte_extent.end;
        de_u64 span{};require(de_u64_sub(&end,&byte_extent.start,&span));require(de_u64_to_size(&span,&length));
        return {bytes_.data()+start,length};
    }
    de_view block(const de_u64& lba) const {
        auto one=de_u64_from_u32(1);de_block_extent extent{};
        if(de_extent_make(&space_,&lba,&one,&extent)!=DE_OK)return {nullptr,0};
        return region(extent);
    }
};
V mbr_entry(const de_mbr_entry& entry,const de_view& raw,bool decoded) {
    auto value=V::object();
    value.put("raw",V::string(hex(raw.data,raw.size))).put("decoded",V::boolean_value(decoded));
    if(!decoded)return value;
    value.put("active",V::boolean_value(entry.active!=0))
        .put("kind",number(static_cast<std::size_t>(entry.kind))).put("issues",number(entry.issues))
        .put("relative_start",exact(entry.relative_start)).put("blocks",exact(entry.blocks))
        .put("range_valid",V::boolean_value(entry.range_valid!=0));
    value.put("start",entry.range_valid?exact(entry.extent.start):V{}).put("end",entry.range_valid?exact(entry.extent.end):V{});
    return value;
}
V mbr_table(const de_mbr_table& table) {
    auto value=V::object(),entries=V::array();
    for(std::size_t i=0;i<4;++i) {
        const auto offset=446+16*i;de_view raw{nullptr,0};
        if(offset<table.raw.size)raw={table.raw.data+offset,std::min<std::size_t>(16,table.raw.size-offset)};
        entries.items.push_back(mbr_entry(table.entries[i],raw,table.signature!=0));
    }
    return value.put("issues",number(table.issues)).put("signature",V::boolean_value(table.signature!=0)).put("entries",std::move(entries));
}
V header(const de_gpt_header& h) {
    auto v=V::object();
    const bool decoded=(h.issues&(DE_GPT_TRUNCATED|DE_GPT_SIGNATURE))==0;
    v.put("issues",number(h.issues)).put("consistent",V::boolean_value(h.consistent!=0))
        .put("fields_decoded",V::boolean_value(decoded));
    if(!decoded)return v;
    return v.put("my_lba",exact(h.my_lba)).put("alternate",exact(h.alternate_lba))
        .put("first",exact(h.first_usable)).put("last",exact(h.last_usable))
        .put("disk_guid",V::string(guid(h.disk_guid))).put("array_lba",exact(h.array_lba))
        .put("array_bytes",(h.issues&DE_GPT_ARRAY_SHAPE)?V{}:exact(h.array_bytes))
        .put("array_blocks",(h.issues&DE_GPT_ARRAY_SHAPE)?V{}:exact(h.array_blocks))
        .put("count",number(h.count)).put("entry_size",number(h.entry_size));
}
V gpt_entry(const de_gpt_entry& e,std::size_t slot) {
    auto value=V::object();
    value.put("slot",number(slot)).put("issues",number(e.issues)).put("first",exact(e.first)).put("last",exact(e.last))
        .put("attributes",exact(e.attributes)).put("range_valid",V::boolean_value(e.range_valid!=0))
        .put("end",e.range_valid?exact(e.extent.end):V{}).put("type_guid",V::string(guid(e.raw.data)))
        .put("unique_guid",V::string(guid(e.raw.data+16))).put("name_raw",V::string(hex(e.raw.data+56,72)));
    de_view name{e.raw.data+56,72};char text[109];int terminated=0;
    const auto status=de_gpt_name_utf8(&name,text,sizeof(text),&terminated);
    value.put("name_status",number(static_cast<std::size_t>(status)))
        .put("name",status==DE_OK?V::string(text):V{}).put("terminated",V::boolean_value(e.name_terminated!=0));
    return value;
}
V candidate(const de_gpt_candidate& c) {
    auto value=V::object(),entries=V::array();std::size_t active=0;
    for(std::size_t i=0;i<c.count;++i)if(c.entries[i].active) {
        ++active;if(entries.items.size()<detail_limit)entries.items.push_back(gpt_entry(c.entries[i],i+1));
    }
    const auto omitted=active-entries.items.size();
    return value.put("issues",number(c.issues)).put("complete",V::boolean_value(c.complete!=0))
        .put("consistent",V::boolean_value(c.consistent!=0)).put("count",number(c.count))
        .put("active_count",number(active)).put("omitted",number(omitted)).put("entries",std::move(entries));
}
}
json::Value observe_partition_map(const std::vector<unsigned char>& bytes,const de_u64& blocks,de_u32 unit) {
    if(unit!=512 && unit!=4096)throw MapObservationError("image_geometry");
    if(bytes.size()>input_limit)throw MapObservationError("image_input_limit");
    const auto scale=de_u64_from_u32(unit);de_u64 capacity{},captured{};
    if(de_u64_mul(&blocks,&scale,&capacity))throw MapObservationError("image_capacity_overflow");
    require(de_u64_from_size(bytes.size(),&captured));
    if(de_u64_compare(&captured,&capacity)>0)throw MapObservationError("image_geometry");
    de_block_space space{};require(de_space_init("captured-image",14,&blocks,unit,&space));Prefix prefix(bytes,space);
    unsigned char digest[32];sha256(bytes.data(),bytes.size(),digest);
    auto out=V::object(),capture=V::object(),geometry=V::object();
    capture.put("bytes",exact(captured)).put("declared_bytes",exact(capacity))
        .put("sha256",V::string("sha256:"+hex(digest,32)))
        .put("complete",V::boolean_value(de_u64_compare(&captured,&capacity)==0))
        .put("source_consistency",V::string("unknown"));
    geometry.put("blocks",exact(blocks)).put("logical_block_bytes",V::string(std::to_string(unit)));
    out.put("schema",V::string("org.disked.captured-map-review/1")).put("capture",std::move(capture)).put("geometry",std::move(geometry));
    const auto zero=de_u64_from_u32(0),one=de_u64_from_u32(1);de_mbr_geometry chs{};de_mbr_table mbr{};
    auto first=prefix.block(zero);const auto mbr_status=de_mbr_read(&first,&space,&chs,&mbr);
    out.put("mbr_status",number(static_cast<std::size_t>(mbr_status))).put("mbr",mbr_status==DE_OK?mbr_table(mbr):V{});
    auto walks=V::array();
    if(mbr_status==DE_OK && mbr.signature)for(unsigned slot=0;slot<4;++slot) {
        const auto& root=mbr.entries[slot];if(!root.active || root.kind!=DE_MBR_EXTENDED || !root.range_valid)continue;
        std::vector<de_ebr_node> nodes(DE_EBR_LIMIT);de_ebr_walk walk{};
        require(de_ebr_init(&mbr,slot,&chs,nodes.data(),nodes.size(),DE_EBR_LIMIT,&walk));
        while(walk.needs_block) {
            const auto pending=walk.pending;const auto view=prefix.block(pending);
            require(view.size?de_ebr_feed(&walk,&pending,&view):de_ebr_unavailable(&walk));
        }
        auto value=V::object(),reported=V::array();
        for(std::size_t i=0;i<std::min(walk.count,detail_limit);++i) {
            auto node=mbr_table(nodes[i].table);node.put("lba",exact(nodes[i].lba));reported.items.push_back(std::move(node));
        }
        const auto omitted=walk.count-reported.items.size();
        value.put("slot",number(slot+1)).put("issues",number(walk.issues)).put("complete",V::boolean_value(walk.complete!=0))
            .put("count",number(walk.count)).put("omitted",number(omitted)).put("nodes",std::move(reported));
        walks.items.push_back(std::move(value));
    }
    out.put("walks",std::move(walks));
    de_gpt_header headers[2]{};de_gpt_candidate candidates[2]{};std::vector<de_gpt_entry> entries[2];
    const de_gpt_limits limits{1024,4096,1048576};auto copies=V::array();
    for(unsigned i=0;i<2;++i) {
        auto lba=one;int status=DE_OK;
        if(i)status=de_u64_sub(&blocks,&one,&lba);
        auto value=V::object();value.put("role",V::string(i?"backup":"primary"));
        if(status!=DE_OK)status=DE_BOUNDS;
        else {value.put("lba",exact(lba));const auto view=prefix.block(lba);status=de_gpt_header_read(&view,&space,&lba,i?DE_GPT_BACKUP:DE_GPT_PRIMARY,&headers[i]);}
        value.put("status",number(static_cast<std::size_t>(status)));
        if(status==DE_OK) {
            candidates[i].header=&headers[i];value.put("header",header(headers[i]));de_block_extent request{};
            const auto requested=de_gpt_request_array(&headers[i],&limits,&request);
            value.put("request_status",number(static_cast<std::size_t>(requested)));
            if(requested==DE_OK) {
                value.put("request_start",exact(request.start)).put("request_end",exact(request.end));
                entries[i].resize(headers[i].count);const auto view=prefix.region(request);
                const auto result=de_gpt_array_read(&headers[i],&limits,&view,entries[i].data(),entries[i].size(),&candidates[i]);
                value.put("array_status",number(static_cast<std::size_t>(result)));
                if(result==DE_OK)value.put("candidate",candidate(candidates[i]));
            }
        }
        copies.items.push_back(std::move(value));
    }
    out.put("copies",std::move(copies));int relation=DE_GPT_INCOMPARABLE;
    const auto compared=de_gpt_compare(&candidates[0],&candidates[1],&relation);
    out.put("compare_status",number(static_cast<std::size_t>(compared)))
        .put("comparison",compared==DE_OK?number(static_cast<std::size_t>(relation)):V{});
    json::Limits bounds;bounds.bytes=48*1024;bounds.depth=16;bounds.values=4096;bounds.string_bytes=512;
    try {json::dump(out,bounds);}catch(const json::Error&) {throw MapObservationError("image_report_limit");}
    return out;
}
}
