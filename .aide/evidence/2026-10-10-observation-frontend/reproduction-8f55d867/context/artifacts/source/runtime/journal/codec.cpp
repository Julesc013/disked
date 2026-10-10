#include "codec.h"
#include "sha256.h"
#include <algorithm>
#include <cstring>

namespace disked { namespace journal { namespace proposal {
namespace {
template<std::size_t N> bool nonzero(const std::array<unsigned char,N>& a) {
    return std::any_of(a.begin(),a.end(),[](unsigned char c){return c!=0;});
}
void put(Bytes& b,std::size_t at,std::uint64_t v,std::size_t n) {
    for(std::size_t i=0;i<n;++i)b[at+i]=static_cast<unsigned char>(v>>(8*i));
}
std::uint64_t get(const Bytes& b,std::size_t at,std::size_t n) {
    std::uint64_t v=0;for(std::size_t i=0;i<n;++i)v|=std::uint64_t(b[at+i])<<(8*i);return v;
}
template<std::size_t N> std::array<unsigned char,N> field(const Bytes& b,std::size_t at) {
    std::array<unsigned char,N> a{};std::copy_n(b.begin()+at,N,a.begin());return a;
}
template<std::size_t N> void store(Bytes& b,std::size_t at,const std::array<unsigned char,N>& a) {
    std::copy(a.begin(),a.end(),b.begin()+at);
}
bool known(std::uint16_t kind) {return (kind>=1 && kind<=9) || kind==32769;}
void shape(std::uint16_t kind,std::uint16_t flags,bool producer) {
    if(flags>1)throw Error("journal_record_flags");
    if(kind>=1 && kind<=9) {if(flags!=1)throw Error("journal_critical_bit");return;}
    if(kind==32769) {if(flags!=0)throw Error("journal_observation_flags");return;}
    if(producer || flags!=0 || kind<32768)throw Error("journal_unknown_kind");
}
void binding_shape(const Bindings& b) {
    if(!nonzero(b.journal) || !nonzero(b.plan) || !nonzero(b.targets) || !nonzero(b.providers))throw Error("journal_empty_binding");
}
bool equal(const Bindings& a,const Bindings& b) {
    return a.journal==b.journal && a.plan==b.plan && a.targets==b.targets && a.providers==b.providers;
}
Bytes exact(Source& source,std::uint64_t at,std::size_t n) {
    if(n>max_payload)throw Error("journal_read_budget");
    Bytes value;try {value=source.read_at(at,n);}catch(...) {throw Error("journal_source_observation_failed");}
    if(value.size()!=n)throw Error("journal_source_length");return value;
}
Digest record_hash(const Digest& header,const Bytes& prefix,const Bytes& payload) {
    Bytes bytes;bytes.reserve(header.size()+prefix.size()+payload.size());
    bytes.insert(bytes.end(),header.begin(),header.end());bytes.insert(bytes.end(),prefix.begin(),prefix.end());
    bytes.insert(bytes.end(),payload.begin(),payload.end());return hash(bytes);
}
}
Digest hash(const Bytes& bytes) {Digest d{};sha256(bytes.data(),bytes.size(),d.data());return d;}
Bytes encode_header(const Bindings& bindings) {
    binding_shape(bindings);Bytes b(header_bytes,0);std::memcpy(b.data(),"DEJPR001",8);
    put(b,8,1,2);put(b,10,0,2);put(b,12,header_bytes,4);put(b,20,max_payload,4);
    store(b,24,bindings.journal);store(b,40,bindings.plan);store(b,72,bindings.targets);store(b,104,bindings.providers);
    store(b,160,hash(Bytes(b.begin(),b.begin()+160)));return b;
}
Bindings decode_header(const Bytes& b) {
    if(b.size()!=header_bytes)throw Error("journal_header_length");
    if(std::memcmp(b.data(),"DEJPR001",8)!=0)throw Error("journal_magic");
    if(get(b,8,2)!=1 || get(b,10,2)!=0)throw Error("journal_version");
    if(get(b,12,4)!=header_bytes || get(b,20,4)!=max_payload)throw Error("journal_header_profile");
    if(get(b,16,4)!=0 || std::any_of(b.begin()+136,b.begin()+160,[](unsigned char c){return c!=0;}))throw Error("journal_header_flags");
    if(hash(Bytes(b.begin(),b.begin()+160))!=field<32>(b,160))throw Error("journal_header_checksum");
    Bindings out;out.journal=field<16>(b,24);out.plan=field<32>(b,40);out.targets=field<32>(b,72);out.providers=field<32>(b,104);
    binding_shape(out);return out;
}
Bytes encode_record(const Digest& header_digest,const Record& record) {
    shape(record.kind,record.flags,true);
    if(!record.sequence || !record.publisher_epoch || !nonzero(record.publisher) || !nonzero(record.previous) || !nonzero(header_digest))throw Error("journal_record_identity");
    if(record.payload.size()>max_payload)throw Error("journal_payload_limit");
    Bytes prefix(prefix_bytes,0);std::memcpy(prefix.data(),"JREC",4);
    put(prefix,4,record.kind,2);put(prefix,6,record.flags,2);put(prefix,8,prefix_bytes,4);put(prefix,12,record.payload.size(),4);
    put(prefix,16,record.sequence,8);store(prefix,24,record.publisher);put(prefix,40,record.publisher_epoch,8);
    store(prefix,48,record.previous);store(prefix,80,hash(record.payload));
    const auto digest=record_hash(header_digest,prefix,record.payload);
    Bytes out=prefix;out.insert(out.end(),record.payload.begin(),record.payload.end());out.insert(out.end(),digest.begin(),digest.end());return out;
}
Scan scan(Source& source,const Bindings& expected,const std::function<bool(const Record&)>& visitor) {
    Scan out;std::uint64_t offset=0;
    try {
        binding_shape(expected);std::uint64_t total=0;
        try {total=source.size();}catch(...) {throw Error("journal_source_observation_failed");}
        if(total>max_source)throw Error("journal_source_budget");
        if(total<header_bytes)throw Error("journal_header_incomplete");
        const auto header=exact(source,0,header_bytes);const auto actual=decode_header(header);
        if(!equal(actual,expected))throw Error("journal_binding_mismatch");
        const auto header_digest=field<32>(header,160);out.last=header_digest;out.verified_bytes=header_bytes;offset=header_bytes;
        while(offset<total) {
            if(out.terminal_record_observed)throw Error("journal_after_terminal");
            if(out.records==max_records)throw Error("journal_record_budget");
            if(total-offset<prefix_bytes) {out.disposition="torn_tail";out.diagnostic="journal_final_prefix_incomplete";out.error_offset=offset;return out;}
            const auto prefix=exact(source,offset,prefix_bytes);
            if(std::memcmp(prefix.data(),"JREC",4)!=0)throw Error("journal_record_magic");
            if(get(prefix,8,4)!=prefix_bytes)throw Error("journal_prefix_length");
            const auto payload_size=get(prefix,12,4);
            if(payload_size>max_payload)throw Error("journal_payload_limit");
            Record record;record.kind=static_cast<std::uint16_t>(get(prefix,4,2));record.flags=static_cast<std::uint16_t>(get(prefix,6,2));shape(record.kind,record.flags,false);
            record.sequence=get(prefix,16,8);record.publisher=field<16>(prefix,24);record.publisher_epoch=get(prefix,40,8);record.previous=field<32>(prefix,48);
            if(!record.publisher_epoch || !nonzero(record.publisher))throw Error("journal_record_identity");
            if(record.sequence!=out.records+1)throw Error("journal_sequence");
            if(record.previous!=out.last)throw Error("journal_previous_digest");
            const auto extent=prefix_bytes+payload_size+trailer_bytes;
            if(total-offset<extent) {out.disposition="torn_tail";out.diagnostic="journal_final_record_incomplete";out.error_offset=offset;return out;}
            record.payload=exact(source,offset+prefix_bytes,static_cast<std::size_t>(payload_size));
            if(hash(record.payload)!=field<32>(prefix,80))throw Error("journal_payload_checksum");
            record.digest=field<32>(exact(source,offset+prefix_bytes+payload_size,trailer_bytes),0);
            if(record_hash(header_digest,prefix,record.payload)!=record.digest)throw Error("journal_record_checksum");
            record.known=known(record.kind);
            if(visitor) {
                bool accepted=false;
                try {accepted=visitor(record);}catch(...) {throw Error("journal_visitor_failed");}
                if(!accepted)throw Error("journal_semantic_rejected");
            }
            ++out.records;out.last=record.digest;offset+=extent;out.verified_bytes=offset;out.terminal_record_observed=record.kind==9;
        }
        out.disposition="valid_prefix";return out;
    } catch(const Error& error) {out.diagnostic=error.what();}
    catch(const std::exception&) {out.diagnostic="journal_source_observation_failed";}
    catch(...) {out.diagnostic="journal_source_observation_failed";}
    out.error_offset=offset;return out;
}
}}}
