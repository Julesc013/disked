#include "runtime/planner/gpt_repair.h"
#include <cstdio>
#include <iostream>
#include <limits>
#include <string>

namespace p=disked::planner::proposal;using V=disked::json::Value;
namespace {
void require(bool ok) {if(!ok)throw p::RepairError("probe_shape");}
const V& field(const V& v,const char* key) {const auto value=v.find(key);require(value!=nullptr);return *value;}
std::string text(const V& v) {require(v.kind==V::Kind::string);return v.text;}
std::uint64_t integer(const V& v) {const auto value=text(v);require(disked::json::decimal_u64(value));return std::stoull(value);}
unsigned digit(char c) {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return 10+static_cast<unsigned>(c-'a');throw p::RepairError("probe_hex");}
p::Bytes unhex(const V& value) {
    const auto s=text(value);require(s.size()%2==0);p::Bytes bytes(s.size()/2);
    for(std::size_t i=0;i<bytes.size();++i)bytes[i]=static_cast<unsigned char>(digit(s[i*2])*16+digit(s[i*2+1]));return bytes;
}
std::string hex(const p::Bytes& bytes) {const char digits[]="0123456789abcdef";std::string out;out.reserve(bytes.size()*2);for(const auto b:bytes){out+=digits[b>>4];out+=digits[b&15];}return out;}
p::GptRepairCapture capture(const V& input) {
    require(input.kind==V::Kind::object && input.fields.size()==9);p::GptRepairCapture c;c.image_id=text(field(input,"image_id"));c.epoch=integer(field(input,"epoch"));c.blocks=integer(field(input,"blocks"));const auto unit=integer(field(input,"block_bytes"));require(unit<=(std::numeric_limits<std::uint32_t>::max)());c.block_bytes=static_cast<std::uint32_t>(unit);
    c.protective_mbr=unhex(field(input,"protective_mbr"));c.primary_header=unhex(field(input,"primary_header"));c.primary_array=unhex(field(input,"primary_array"));c.backup_header=unhex(field(input,"backup_header"));c.backup_array=unhex(field(input,"backup_array"));return c;
}
}
int main() {
    disked::json::Limits limits;limits.bytes=16777216;limits.string_bytes=4194302;limits.values=8192;
    try {
        std::string raw;char block[4096];while(std::cin.read(block,sizeof(block)) || std::cin.gcount()) {require(raw.size()+static_cast<std::size_t>(std::cin.gcount())<=limits.bytes);raw.append(block,static_cast<std::size_t>(std::cin.gcount()));}
        auto input=disked::json::parse(raw,limits);require(input.kind==V::Kind::object);auto c=capture(field(input,"capture"));const auto mode=text(field(input,"mode"));
        if(mode=="fingerprint") {std::cout<<disked::json::dump(V::object().put("capture_digest",V::string(p::gpt_repair_capture_digest(c))))<<'\n';return 0;}
        require(mode=="plan" || mode=="mutate_after_build" || mode=="check_binding");p::GptRepairSelection selected;
        const auto source=text(field(input,"source"));require(source=="primary" || source=="backup");selected.source=source=="primary"?p::GptCopy::primary:p::GptCopy::backup;
        const auto decision=input.find("selection_decision_digest");if(decision && decision->kind!=V::Kind::null)selected.decision_digest=text(*decision);
        const auto before=p::gpt_repair_capture_digest(c);p::GptRepairPlan plan(c,text(field(input,"expected_capture_digest")),selected);auto output=V::object().put("definition",plan.definition()).put("plan_digest",V::string(plan.digest())).put("input_unchanged",V::boolean_value(before==p::gpt_repair_capture_digest(c))).put("matches_original",V::boolean_value(plan.matches_capture(c)));
        auto patches=V::array();for(const auto& patch:plan.patches())patches.items.push_back(V::object().put("id",V::string(patch.id)).put("before_hex",V::string(hex(patch.before))).put("after_hex",V::string(hex(patch.after))));output.put("patch_bytes",patches);
        if(mode=="mutate_after_build") {const auto definition=disked::json::dump(plan.definition());c.primary_header[0]^=1;c.primary_array[0]^=1;output.put("matches_changed",V::boolean_value(plan.matches_capture(c))).put("definition_unchanged",V::boolean_value(definition==disked::json::dump(plan.definition())));}
        if(mode=="check_binding")output.put("matches_changed",V::boolean_value(plan.matches_capture(capture(field(input,"changed_capture")))));
        std::cout<<disked::json::dump(output,limits)<<'\n';return 0;
    }catch(const p::RepairError& error) {std::cout<<disked::json::dump(V::object().put("status",V::string("refused")).put("code",V::string(error.what())).put("authorizes_effects",V::boolean_value(false)))<<'\n';return 3;}
     catch(const disked::json::Error& error) {std::cout<<disked::json::dump(V::object().put("status",V::string("refused")).put("code",V::string(error.code)))<<'\n';return 2;}
     catch(const std::exception&) {std::fputs("probe internal failure\n",stderr);return 4;}
}
