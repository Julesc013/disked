#include "codec.h"
#include "json.h"
#include <algorithm>
#include <iostream>
#include <limits>

using disked::json::Value;
namespace p=disked::journal::proposal;
namespace {
std::string hex(const p::Bytes& b) {
    const char* digits="0123456789abcdef";std::string out;out.reserve(b.size()*2);
    for(const auto c:b) {out+=digits[c>>4];out+=digits[c&15];}return out;
}
template<std::size_t N> std::string hex(const std::array<unsigned char,N>& b) {return hex(p::Bytes(b.begin(),b.end()));}
std::string string(const Value& v,const std::string& name) {
    const auto* s=v.find(name);if(!s || s->kind!=Value::Kind::string)throw p::Error("probe_string");return s->text;
}
std::uint64_t integer(const Value& v,const std::string& name) {
    const auto s=string(v,name);if(!disked::json::decimal_u64(s))throw p::Error("probe_u64");return std::stoull(s);
}
p::Bytes bytes(const std::string& text) {
    if(text.size()%2 || text.find_first_not_of("0123456789abcdef")!=std::string::npos)throw p::Error("probe_hex");
    p::Bytes out;out.reserve(text.size()/2);
    const std::string digits="0123456789abcdef";
    for(std::size_t i=0;i<text.size();i+=2)out.push_back(static_cast<unsigned char>((digits.find(text[i])<<4)|digits.find(text[i+1])));return out;
}
template<std::size_t N> std::array<unsigned char,N> field(const Value& v,const std::string& name) {
    const auto b=bytes(string(v,name));if(b.size()!=N)throw p::Error("probe_field_length");
    std::array<unsigned char,N> out{};std::copy(b.begin(),b.end(),out.begin());return out;
}
p::Bindings bindings(const Value& v) {
    if(v.kind!=Value::Kind::object)throw p::Error("probe_bindings");
    p::Bindings b;b.journal=field<16>(v,"journal");b.plan=field<32>(v,"plan");b.targets=field<32>(v,"targets");b.providers=field<32>(v,"providers");return b;
}
Value report(const p::Bindings& b) {
    return Value::object().put("journal",Value::string(hex(b.journal))).put("plan",Value::string(hex(b.plan)))
        .put("targets",Value::string(hex(b.targets))).put("providers",Value::string(hex(b.providers)));
}
class Memory final:public p::Source {
public:
    p::Bytes data;std::uint64_t announced=0,calls=0,largest=0,read_bytes=0;std::string fault;
    std::uint64_t size() override {if(fault=="size-throw")throw std::runtime_error("fixture");return announced;}
    p::Bytes read_at(std::uint64_t at,std::size_t n) override {
        ++calls;largest=(std::max)(largest,static_cast<std::uint64_t>(n));read_bytes+=n;
        if(fault=="throw")throw std::runtime_error("fixture");
        if(at>data.size() || n>data.size()-at)return {};
        p::Bytes b(data.begin()+static_cast<std::size_t>(at),data.begin()+static_cast<std::size_t>(at)+n);
        if(fault=="short" && !b.empty())b.pop_back();
        if(fault=="oversized")b.push_back(0);return b;
    }
};
Value request(const Value& v) {
    const auto op=string(v,"op");
    if(op!="record" && !v.find("bindings"))throw p::Error("probe_bindings");
    if(op=="header") {
        const auto b=p::encode_header(bindings(*v.find("bindings")));
        return Value::object().put("bytes",Value::string(hex(b))).put("decoded",report(p::decode_header(b)));
    }
    if(op=="record") {
        p::Record r;const auto k=integer(v,"kind"),f=integer(v,"flags");
        if(k>65535 || f>65535)throw p::Error("probe_u16");r.kind=static_cast<std::uint16_t>(k);r.flags=static_cast<std::uint16_t>(f);
        r.sequence=integer(v,"sequence");r.publisher_epoch=integer(v,"publisher_epoch");r.publisher=field<16>(v,"publisher");r.previous=field<32>(v,"previous");r.payload=bytes(string(v,"payload"));
        return Value::object().put("bytes",Value::string(hex(p::encode_record(field<32>(v,"header_digest"),r))));
    }
    if(op!="scan")throw p::Error("probe_operation");
    Memory m;m.data=bytes(string(v,"bytes"));m.announced=v.find("announced")?integer(v,"announced"):m.data.size();
    if(v.find("fault"))m.fault=string(v,"fault");
    auto records=Value::array();const auto reject=v.find("reject_sequence")?integer(v,"reject_sequence"):0;
    const auto out=p::scan(m,bindings(*v.find("bindings")),[&](const p::Record& r) {
        if(r.sequence==reject)return false;
        if(m.fault=="visitor-throw")throw std::runtime_error("fixture");
        if(records.items.size()<64)records.items.push_back(Value::object().put("kind",Value::string(std::to_string(r.kind))).put("known",Value::boolean_value(r.known))
            .put("sequence",Value::string(std::to_string(r.sequence))).put("publisher",Value::string(hex(r.publisher))).put("publisher_epoch",Value::string(std::to_string(r.publisher_epoch)))
            .put("payload_digest",Value::string(hex(p::hash(r.payload)))).put("digest",Value::string(hex(r.digest))));return true;
    });
    return Value::object().put("scope",Value::string("private-framing-only")).put("authorizes_effects",Value::boolean_value(false))
        .put("disposition",Value::string(out.disposition)).put("diagnostic",Value::string(out.diagnostic))
        .put("records",Value::string(std::to_string(out.records))).put("verified_bytes",Value::string(std::to_string(out.verified_bytes)))
        .put("error_offset",Value::string(std::to_string(out.error_offset))).put("last_digest",Value::string(hex(out.last)))
        .put("terminal_record_observed",Value::boolean_value(out.terminal_record_observed)).put("visited",records)
        .put("metadata_omitted",Value::boolean_value(out.records>64)).put("read_calls",Value::string(std::to_string(m.calls)))
        .put("largest_read",Value::string(std::to_string(m.largest))).put("read_bytes",Value::string(std::to_string(m.read_bytes)));
}
}
int main() {
    disked::json::Limits limits;limits.bytes=2097152;limits.string_bytes=2096128;
    std::string line;
    while(std::getline(std::cin,line)) {
        Value reply;
        try {reply=request(disked::json::parse(line,limits));}
        catch(const std::exception& e) {reply=Value::object().put("error",Value::string(e.what()));}
        std::cout<<disked::json::dump(reply,limits)<<'\n';
    }
}
