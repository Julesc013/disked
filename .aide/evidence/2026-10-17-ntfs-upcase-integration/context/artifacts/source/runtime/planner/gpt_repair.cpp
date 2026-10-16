#include "gpt_repair.h"
#include "portable/gpt/gpt.h"
#include "portable/mbr/mbr.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <cstring>
#include <limits>
#include <utility>

namespace disked { namespace planner { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code) {throw RepairError(code);}
void require(bool condition,const char* code) {if(!condition)fail(code);}
de_view view(const Bytes& bytes) {return {bytes.data(),bytes.size()};}
std::string hash(const unsigned char* bytes,std::size_t size) {
    unsigned char digest[32];disked::sha256(size?bytes:reinterpret_cast<const unsigned char*>(""),size,digest);
    const char digits[]="0123456789abcdef";std::string out="sha256:";
    for(const auto b:digest) {out+=digits[b>>4];out+=digits[b&15];}return out;
}
std::string hash(const Bytes& bytes) {return hash(bytes.data(),bytes.size());}
std::string hash(const std::string& bytes) {return hash(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size());}
bool digest_valid(const std::string& value) {
    return value.size()==71 && value.compare(0,7,"sha256:")==0 && value.find_first_not_of("0123456789abcdef",7)==value.npos && value.substr(7)!=std::string(64,'0');
}
V number(std::uint64_t value) {return V::string(std::to_string(value));}
void capture_limits(const GptRepairCapture& c) {
    require(!c.image_id.empty() && c.image_id.size()<=128 && c.image_id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:/@+-")==c.image_id.npos,"repair_input_invalid");
    require(c.epoch && c.blocks>=3 && c.block_bytes>=512 && c.block_bytes<=1048576,"repair_input_invalid");
    for(const auto b:{&c.protective_mbr,&c.primary_header,&c.backup_header})require(b->size()<=1048576,"repair_budget");
    for(const auto b:{&c.primary_array,&c.backup_array})require(b->size()<=2097151,"repair_budget");
}
V metadata(const GptRepairCapture& c) {
    capture_limits(c);auto v=V::object().put("schema",V::string("org.disked.gpt-repair-capture-prototype/1"))
        .put("image_id",V::string(c.image_id)).put("epoch",number(c.epoch)).put("blocks",number(c.blocks)).put("block_bytes",number(c.block_bytes));
    for(const auto item:{std::make_pair("protective_mbr",&c.protective_mbr),std::make_pair("primary_header",&c.primary_header),std::make_pair("primary_array",&c.primary_array),std::make_pair("backup_header",&c.backup_header),std::make_pair("backup_array",&c.backup_array)})
        v.put(item.first,V::object().put("bytes",number(item.second->size())).put("sha256",V::string(hash(*item.second))));
    return v;
}
de_u64 exact(std::uint64_t value) {de_u64 n{};const auto text=std::to_string(value);require(!de_u64_parse(text.data(),text.size(),&n),"repair_input_invalid");return n;}
std::uint64_t native(const de_u64& value) {char text[21];require(!de_u64_format(&value,text,sizeof(text)),"repair_offset_overflow");return std::stoull(text);}
std::uint64_t byte_offset(std::uint64_t lba,std::uint32_t unit) {
    require(lba<=(std::numeric_limits<std::uint64_t>::max)()/unit,"repair_offset_overflow");return lba*unit;
}
void crc_header(Bytes& bytes,std::uint32_t size) {
    require(size>=92 && size<=bytes.size(),"repair_target_structure");std::fill(bytes.begin()+16,bytes.begin()+20,static_cast<unsigned char>(0));
    de_view prefix{bytes.data(),size};de_u32 crc=0;require(!de_gpt_crc32(&prefix,&crc),"repair_simulation_refused");
    for(unsigned i=0;i<4;++i)bytes[16+i]=static_cast<unsigned char>(crc>>(i*8));
}
void protective(const GptRepairCapture& c,const de_block_space& space) {
    require(c.protective_mbr.size()==c.block_bytes,"repair_protective_mbr");auto bytes=view(c.protective_mbr);de_mbr_table table{};
    const de_mbr_geometry unknown_geometry{};
    require(!de_mbr_read(&bytes,&space,&unknown_geometry,&table) && table.signature && !table.issues,"repair_protective_mbr");
    unsigned count=0;for(const auto& entry:table.entries)if(entry.active && entry.kind==DE_MBR_GPT)++count;
    require(count==1,"repair_protective_mbr");
}
struct Candidate {
    de_gpt_header header{};
    de_gpt_candidate candidate{};
    std::vector<de_gpt_entry> entries;
};
void read_header(Candidate& out,const Bytes& bytes,const de_block_space& space,int role,const char* code="repair_target_structure") {
    auto raw=view(bytes);const auto lba=role==DE_GPT_PRIMARY?exact(1):exact(native(space.blocks)-1);
    require(!de_gpt_header_read(&raw,&space,&lba,role,&out.header),code);
}
void read_array(Candidate& out,const Bytes& bytes,const char* code="repair_target_structure") {
    const de_gpt_limits limits{1024,4096,1048576};de_block_extent extent{};
    const auto status=de_gpt_request_array(&out.header,&limits,&extent);
    require(status!=DE_BUFFER,"repair_budget");require(!status,code);
    out.entries.resize(out.header.count);auto raw=view(bytes);
    require(!de_gpt_array_read(&out.header,&limits,&raw,out.entries.data(),out.entries.size(),&out.candidate),code);
}
bool compatible(const de_gpt_header& a,const de_gpt_header& b) {
    return a.header_size==b.header_size && a.count==b.count && a.entry_size==b.entry_size &&
        !std::memcmp(a.disk_guid,b.disk_guid,16) && !de_u64_compare(&a.first_usable,&b.first_usable) && !de_u64_compare(&a.last_usable,&b.last_usable);
}
const char* name(GptCopy copy) {return copy==GptCopy::primary?"primary":"backup";}
V names(const std::vector<std::string>& values) {auto out=V::array();for(const auto& s:values)out.items.push_back(V::string(s));return out;}
void patch(std::vector<GptRepairPatch>& out,const std::string& id,std::uint64_t offset,const Bytes& before,const Bytes& after,std::size_t size) {
    require(size<=before.size() && size<=after.size() && size<=(std::numeric_limits<std::uint64_t>::max)()-offset,"repair_offset_overflow");
    if(std::equal(before.begin(),before.begin()+size,after.begin()))return;
    GptRepairPatch p;p.id=id;p.offset=offset;p.before.assign(before.begin(),before.begin()+size);p.after.assign(after.begin(),after.begin()+size);
    if(!out.empty())p.depends_on.push_back(out.back().id);out.push_back(std::move(p));
}
}
std::string gpt_repair_capture_digest(const GptRepairCapture& c) {return hash("DiskEd.gpt-repair.capture/1\n"+json::dump(metadata(c)));}
bool GptRepairPlan::matches_capture(const GptRepairCapture& c) const {
    try {return capture_digest_==gpt_repair_capture_digest(c);}catch(const RepairError&) {return false;}
}
GptRepairPlan::GptRepairPlan(const GptRepairCapture& c,const std::string& expected,const GptRepairSelection& selection) {
    require(selection.source==GptCopy::primary || selection.source==GptCopy::backup,"repair_source_selection");
    require(digest_valid(expected) && (selection.decision_digest.empty() || digest_valid(selection.decision_digest)),"repair_input_invalid");
    const auto fingerprint=gpt_repair_capture_digest(c);require(fingerprint==expected,"repair_capture_mismatch");
    // Check complete byte-space representability without allocating the image.
    byte_offset(c.blocks,c.block_bytes);de_block_space space{};const auto blocks=exact(c.blocks);
    require(!de_space_init(c.image_id.data(),c.image_id.size(),&blocks,c.block_bytes,&space),"repair_input_invalid");protective(c,space);
    const bool primary=selection.source==GptCopy::primary;const auto& source_header=primary?c.primary_header:c.backup_header;
    const auto& source_array=primary?c.primary_array:c.backup_array;const auto& target_header=primary?c.backup_header:c.primary_header;
    const auto& target_array=primary?c.backup_array:c.primary_array;const int source_role=primary?DE_GPT_PRIMARY:DE_GPT_BACKUP,target_role=primary?DE_GPT_BACKUP:DE_GPT_PRIMARY;
    Candidate source,target,original;read_header(source,source_header,space,source_role,"repair_source_unusable");
    require(source.header.consistent,"repair_source_unusable");read_array(source,source_array,"repair_source_unusable");require(source.candidate.complete && source.candidate.consistent,"repair_source_unusable");
    read_header(original,target_header,space,target_role);
    require((original.header.issues & ~static_cast<de_u32>(DE_GPT_HEADER_CRC))==0,"repair_target_structure");
    require(compatible(source.header,original.header),"repair_layout_conflict");
    Bytes repaired_header=target_header;crc_header(repaired_header,original.header.header_size);read_header(target,repaired_header,space,target_role);require(target.header.consistent,"repair_target_structure");read_array(target,target_array);
    require(target.candidate.complete,"repair_target_structure");
    const auto array_size=static_cast<std::size_t>(native(source.header.array_bytes));
    require(std::all_of(target_array.begin()+array_size,target_array.end(),[](unsigned char b){return b==0;}),"repair_target_structure");
    const bool differs=!std::equal(source_array.begin(),source_array.begin()+array_size,target_array.begin());
    require(!(original.header.consistent && target.candidate.consistent && differs && selection.decision_digest.empty()),"repair_selection_required");
    // Preserve all target-role layout fields. Only the array checksum and its
    // dependent header checksum change; unadvertised array padding is untouched.
    for(unsigned i=0;i<4;++i)repaired_header[88+i]=static_cast<unsigned char>(source.header.array_crc>>(i*8));crc_header(repaired_header,original.header.header_size);
    Bytes repaired_array=target_array;std::copy(source_array.begin(),source_array.begin()+array_size,repaired_array.begin());
    std::vector<GptRepairPatch> patches;patch(patches,"target-array",byte_offset(native(original.header.array_lba),c.block_bytes),target_array,repaired_array,array_size);
    patch(patches,"target-header",byte_offset(native(original.header.observed_lba),c.block_bytes),target_header,repaired_header,original.header.header_size);
    Candidate result;read_header(result,repaired_header,space,target_role);require(result.header.consistent,"repair_simulation_refused");read_array(result,repaired_array);require(result.candidate.complete && result.candidate.consistent,"repair_simulation_refused");
    int comparison=DE_GPT_INCOMPARABLE;require(!de_gpt_compare(primary?&source.candidate:&result.candidate,primary?&result.candidate:&source.candidate,&comparison) && comparison==DE_GPT_AGREE,"repair_simulation_refused");
    auto definition=V::object().put("schema",V::string("org.disked.gpt-repair-preview-prototype/1")).put("operation",V::string("table.gpt.repair"))
        .put("profile",V::string("gpt-repair-planning-prototype/1")).put("capture",metadata(c)).put("capture_digest",V::string(fingerprint))
        .put("authoritative_copy",V::string(name(selection.source))).put("target_copy",V::string(primary?"backup":"primary"))
        .put("selection_decision_digest",selection.decision_digest.empty()?V{}:V::string(selection.decision_digest))
        .put("status",V::string(patches.empty()?"no_change":"repair_preview"));
    auto regions=V::array();for(const auto& p:patches)regions.items.push_back(V::object().put("id",V::string(p.id)).put("offset",number(p.offset)).put("bytes",number(p.before.size()))
        .put("before_sha256",V::string(hash(p.before))).put("after_sha256",V::string(hash(p.after))).put("depends_on",names(p.depends_on)));
    definition.put("patches",regions).put("execution_requirements",names({"fresh-exact-image-and-recapture","exclusive-access-and-resolved-dependencies","original-metadata-backup","accepted-journal-and-recovery-policy","admitted-provider-byte-write-scope","exact-plan-review-grant-admission","flush-reread-independent-verification"}))
        .put("simulation",V::object().put("type",V::string("shared-parser-byte-overlay")).put("both_copies_consistent",V::boolean_value(true)).put("both_copies_agree",V::boolean_value(true))
             .put("coverage",V::string("supplied-captures-only")).put("independent_verification",V::boolean_value(false)).put("whole_device_valid",V::boolean_value(false)))
        .put("authorizes_effects",V::boolean_value(false)).put("writer_admitted",V::boolean_value(false)).put("qualifies_durability",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));
    capture_digest_=fingerprint;digest_=hash(json::dump(definition));definition_=std::move(definition);patches_=std::move(patches);
}
}}}
