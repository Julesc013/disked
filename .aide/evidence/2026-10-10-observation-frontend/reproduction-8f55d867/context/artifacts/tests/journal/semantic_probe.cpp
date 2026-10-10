#include "semantics.h"
#include <algorithm>
#include <iostream>

namespace p=disked::journal::proposal;
using V=disked::json::Value;
namespace {
const V& get(const V& v,const char* key) {const auto x=v.find(key);if(!x)throw p::Error("probe_field");return *x;}
std::string str(const V& v,const char* key) {const auto& x=get(v,key);if(x.kind!=V::Kind::string)throw p::Error("probe_string");return x.text;}
std::uint64_t num(const V& v,const char* key) {const auto s=str(v,key);if(!disked::json::decimal_u64(s))throw p::Error("probe_integer");return std::stoull(s);}
p::Bytes unhex(const std::string& s) {
    if(s.size()%2 || s.find_first_not_of("0123456789abcdef")!=s.npos)throw p::Error("probe_hex");
    const std::string digits="0123456789abcdef";p::Bytes out;out.reserve(s.size()/2);
    for(std::size_t i=0;i<s.size();i+=2)out.push_back(static_cast<unsigned char>(digits.find(s[i])*16+digits.find(s[i+1])));return out;
}
template<std::size_t N> std::array<unsigned char,N> field(const V& v,const char* key) {const auto b=unhex(str(v,key));if(b.size()!=N)throw p::Error("probe_length");std::array<unsigned char,N> out{};std::copy(b.begin(),b.end(),out.begin());return out;}
std::string hex(const p::Digest& d) {return p::digest_text(d).substr(7);}
class Memory final:public p::Source {
public:
    p::Bytes data;std::uint64_t announced=0,calls=0,largest=0;std::string fault;
    std::uint64_t size() override {if(fault=="size-throw")throw p::Error("fixture");return announced;}
    p::Bytes read_at(std::uint64_t offset,std::size_t n) override {
        ++calls;largest=(std::max)(largest,static_cast<std::uint64_t>(n));if(fault=="throw")throw p::Error("fixture");
        if(offset>data.size() || n>data.size()-offset)return {};
        p::Bytes out(data.begin()+static_cast<std::size_t>(offset),data.begin()+static_cast<std::size_t>(offset)+n);
        if(fault=="short" && !out.empty())out.pop_back();if(fault=="oversized")out.push_back(0);return out;
    }
};
V request(const V& v) {
    const p::Definition definition(get(v,"expected_plan"));const auto& b=get(v,"bindings");p::Bindings expected;
    expected.journal=field<16>(b,"journal");expected.plan=field<32>(b,"plan");expected.targets=field<32>(b,"targets");expected.providers=field<32>(b,"providers");
    const auto& pub=get(v,"publisher");p::PublisherBinding publisher;publisher.identity=field<16>(pub,"identity");publisher.epoch=num(pub,"epoch");
    Memory memory;memory.data=unhex(str(v,"bytes"));memory.announced=v.find("announced")?num(v,"announced"):memory.data.size();if(v.find("fault"))memory.fault=str(v,"fault");
    const auto out=p::scan_semantics(memory,definition,expected,publisher);
    return V::object().put("projection",out.projection).put("semantic_diagnostic",V::string(out.semantic_diagnostic))
        .put("disposition",V::string(out.framing.disposition)).put("diagnostic",V::string(out.framing.diagnostic)).put("records",V::string(std::to_string(out.framing.records)))
        .put("verified_bytes",V::string(std::to_string(out.framing.verified_bytes))).put("error_offset",V::string(std::to_string(out.framing.error_offset)))
        .put("last_digest",V::string(hex(out.framing.last))).put("terminal_record_observed",V::boolean_value(out.framing.terminal_record_observed))
        .put("read_calls",V::string(std::to_string(memory.calls))).put("largest_read",V::string(std::to_string(memory.largest)));
}
}
int main() {
    disked::json::Limits limits;limits.bytes=8388608;limits.string_bytes=8000000;limits.values=262144;
    std::string line;while(std::getline(std::cin,line)) {
        V out;try {out=request(disked::json::parse(line,limits));}catch(const std::exception& error) {out=V::object().put("error",V::string(error.what()));}
        std::cout<<disked::json::dump(out,limits)<<'\n';
    }
}
