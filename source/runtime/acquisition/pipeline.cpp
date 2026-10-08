#include "pipeline.h"
#include "sha256.h"
#include <algorithm>
#include <limits>
#include <set>

namespace disked { namespace acquisition {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code) {throw Error(code);}
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)fail("acquisition_shape");return *p;}
std::string text(const V& v) {if(v.kind!=V::Kind::string)fail("acquisition_shape");return v.text;}
std::uint64_t integer(const V& v) {
    const auto s=text(v);if(!json::decimal_u64(s))fail("acquisition_integer");
    return std::stoull(s);
}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())fail("acquisition_shape");
    for(const auto name:names)field(v,name);
}
void token(const V& v) {
    const auto s=text(v);if(s.empty() || s.size()>256 || !json::valid_utf8(s))fail("acquisition_identity");
    for(const auto c:s)if(static_cast<unsigned char>(c)<32 || c==127)fail("acquisition_identity");
}
std::string hash(const unsigned char* p,std::size_t size) {
    unsigned char digest[32];sha256(p,size,digest);const char alphabet[]="0123456789abcdef";
    std::string out="sha256:";for(const auto b:digest) {out+=alphabet[b>>4];out+=alphabet[b&15];}return out;
}
std::string hash(const std::string& s) {return hash(reinterpret_cast<const unsigned char*>(s.data()),s.size());}
std::string hash(const std::vector<unsigned char>& bytes) {return hash(bytes.data(),bytes.size());}
json::Limits limits() {json::Limits out;out.bytes=16384;out.depth=10;out.values=512;out.string_bytes=512;return out;}
std::string encode(const V& v) {return json::dump(v,limits());}
const char* roles[]={"source","destination","map","host","executable","provider"};
void resources(const V& value,std::uint64_t bytes) {
    keys(value,{"source","destination","map","host","executable","provider"});
    std::set<std::string> written;
    for(unsigned i=0;i<6;++i) {
        const auto& b=field(value,roles[i]);keys(b,{"identity","epoch","access","start","end","aliases","failure_domain","verification"});
        token(field(b,"identity"));token(field(b,"epoch"));token(field(b,"failure_domain"));
        const char* access=i==0?"read":i==1?"create-write":i==2?"create-append":i==4?"read":"observe";
        if(text(field(b,"access"))!=access)fail("acquisition_access");
        const auto start=integer(field(b,"start")),end=integer(field(b,"end"));
        if(start!=0 || end!=(i<2?bytes:0))fail("acquisition_footprint");
        const char* verification=i==0?"identity-epoch":i==1?"readback-sha256":i==2?"ordered-hash-chain":"identity-epoch";
        if(text(field(b,"verification"))!=verification)fail("acquisition_verification");
        const auto& aliases=field(b,"aliases");
        if(aliases.kind!=V::Kind::array || aliases.items.empty() || aliases.items.size()>16)fail("acquisition_aliases_unknown");
        std::set<std::string> unique;bool has_identity=false;
        for(const auto& a:aliases.items) {token(a);const auto s=text(a);if(!unique.insert(s).second)fail("acquisition_aliases_unknown");has_identity|=s==text(field(b,"identity"));}
        if(!has_identity)fail("acquisition_aliases_unknown");
        if(i==1 || i==2)for(const auto& a:unique)if(!written.insert(a).second)fail("acquisition_alias");
    }
    for(unsigned i=0;i<6;++i)if(i!=1 && i!=2)
        for(const auto& a:field(field(value,roles[i]),"aliases").items)
            if(written.count(text(a)))fail("acquisition_alias");
}
void stable_outputs(const V& planned,const V& active,std::uint64_t bytes) {
    resources(active,bytes);
    for(const auto role:roles) {
        const auto& a=field(active,role);const auto& p=field(planned,role);
        if(std::string(role)!="destination" && std::string(role)!="map") {
            if(encode(a)!=encode(p))fail("acquisition_binding_changed");
        } else {
            for(const char* key:{"access","start","end","failure_domain","verification"})
                if(encode(field(a,key))!=encode(field(p,key)))fail("acquisition_binding_changed");
        }
    }
}
void fresh(Ports& ports,const V& active) {
    if(encode(ports.observe())!=encode(active))fail("acquisition_binding_changed");
}
struct Chunk {
    std::uint64_t offset=0;
    std::uint32_t size=0,retries=0;
    std::uint64_t read_bytes=0;
    std::string digest,error;
    bool substituted=false;
};
V chunk_value(const Chunk& c) {
    return V::object().put("offset",number(c.offset)).put("length",number(c.size))
        .put("read_bytes",number(c.read_bytes)).put("retries",number(c.retries))
        .put("sha256",V::string(c.digest)).put("state",V::string(c.substituted?"substituted":"read"))
        .put("read_error",c.error.empty()?V{}:V::string(c.error));
}
Chunk chunk(const V& v,const Plan& p,std::uint64_t offset) {
    keys(v,{"offset","length","read_bytes","retries","sha256","state","read_error"});Chunk c;
    c.offset=integer(field(v,"offset"));const auto n=integer(field(v,"length")),retry=integer(field(v,"retries"));
    if(offset>=p.bytes || c.offset!=offset || n!=std::min<std::uint64_t>(p.chunk_bytes,p.bytes-offset) || retry>p.retries)fail("acquisition_map_geometry");
    c.size=static_cast<std::uint32_t>(n);c.retries=static_cast<std::uint32_t>(retry);c.read_bytes=integer(field(v,"read_bytes"));
    if(c.read_bytes>n)fail("acquisition_map_geometry");
    c.digest=text(field(v,"sha256"));if(c.digest.size()!=71 || c.digest.substr(0,7)!="sha256:")fail("acquisition_map_digest");
    for(std::size_t i=7;i<c.digest.size();++i)if(!((c.digest[i]>='0' && c.digest[i]<='9') || (c.digest[i]>='a' && c.digest[i]<='f')))fail("acquisition_map_digest");
    const auto state=text(field(v,"state"));if(state!="read" && state!="substituted")fail("acquisition_map_state");
    c.substituted=state=="substituted";const auto& error=field(v,"read_error");
    if(error.kind!=V::Kind::null) {token(error);c.error=text(error);}
    if(c.substituted) {
        if(!p.substitute || c.error.empty())fail("acquisition_map_state");
        const std::vector<unsigned char> zeros(c.size,0);if(hash(zeros)!=c.digest)fail("acquisition_map_substitution");
    }
    else if(!c.error.empty() || c.read_bytes!=n)fail("acquisition_map_state");
    return c;
}
void verify(Ports& ports,const Chunk& c,Outcome& out,bool source) {
    auto r=source?ports.read_source(c.offset,c.size):ports.read_destination(c.offset,c.size);
    if(source)out.attempt_read_bytes+=r.bytes.size();
    if(!r.error.empty() || r.bytes.size()!=c.size || hash(r.bytes)!=c.digest)
        fail(source?"acquisition_resume_source_changed":"acquisition_destination_verification");
    if(!source)out.attempt_verified_bytes+=c.size;
}
const std::string initial_hash="sha256:"+std::string(64,'0');
class Ledger {
    Ports& ports_;
public:
    std::string previous=initial_hash;
    std::uint64_t sequence=0;
    explicit Ledger(Ports& ports):ports_(ports) {}
    void require(std::uint64_t count) const {
        if(sequence>1048576 || count>1048576-sequence)fail("acquisition_map_limit");
    }
    V accept(const Record& r) {
        if(r.bytes.size()>16384)fail("acquisition_map_limit");
        auto v=json::parse(r.bytes,limits());keys(v,{"schema","type","sequence","previous","payload"});
        if(text(field(v,"schema"))!="org.disked.acquisition-record-prototype/1" ||
           integer(field(v,"sequence"))!=sequence || text(field(v,"previous"))!=previous)fail("acquisition_map_chain");
        // Reject alternative lexemes/order/whitespace in the private exact-byte format.
        if(encode(v)!=r.bytes)fail("acquisition_map_encoding");
        previous=hash(r.bytes);++sequence;return v;
    }
    void append(const char* type,V payload) {
        require(1);
        auto v=V::object().put("schema",V::string("org.disked.acquisition-record-prototype/1"))
            .put("type",V::string(type)).put("sequence",number(sequence)).put("previous",V::string(previous)).put("payload",std::move(payload));
        const auto bytes=encode(v);ports_.append_record(bytes);ports_.flush_map();previous=hash(bytes);++sequence;
    }
};
void checkpoint(Ports& ports,Ledger& ledger,const Chunk& c,Outcome& out,const V& active) {
    fresh(ports,active);ports.flush_destination();verify(ports,c,out,false);fresh(ports,active);
    ledger.append("checkpoint",chunk_value(c));out.checkpoint_bytes+=c.size;
    if(c.substituted)out.substituted_bytes+=c.size;else out.source_bytes+=c.size;
    out.uncertain_effect=false;
}
}
Plan prepare(const V& value) {
    keys(value,{"schema","capture_epoch","resources","bytes","chunk_bytes","read_policy","retry_limit","substitution"});Plan p;
    if(text(field(value,"schema"))!="org.disked.acquisition-plan-prototype/1")fail("acquisition_plan_version");
    token(field(value,"capture_epoch"));p.bytes=integer(field(value,"bytes"));
    if(p.bytes>static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)()))fail("acquisition_size");
    const auto n=integer(field(value,"chunk_bytes")),retry=integer(field(value,"retry_limit"));
    if(n!=4096 && n!=65536 && n!=1048576)fail("acquisition_chunk_limit");
    if(retry>3)fail("acquisition_retry_limit");p.chunk_bytes=static_cast<std::uint32_t>(n);p.retries=static_cast<std::uint32_t>(retry);
    // Streaming map traversal is bounded by one million records, not image RAM.
    const auto chunks=p.bytes/n+(p.bytes%n?1:0);if(chunks>(1048576-2)/2)fail("acquisition_map_limit");
    const auto policy=text(field(value,"read_policy"));if(policy!="ordinary" && policy!="failing-read-mostly")fail("acquisition_read_policy");
    p.failing_media=policy=="failing-read-mostly";if(p.failing_media && retry)fail("acquisition_aggressive_reread_not_admitted");
    const auto substitution=text(field(value,"substitution"));if(substitution!="stop" && substitution!="zero-fill")fail("acquisition_substitution");
    p.substitute=substitution=="zero-fill";resources(field(value,"resources"),p.bytes);
    p.definition=value;p.digest=hash(encode(value));return p;
}
Outcome execute(const Plan& input,const Grant& grant,Ports& ports,bool resume) {
    Outcome out;bool outputs=false;Ledger ledger(ports);
    try {
        const auto p=prepare(input.definition);
        if(input.digest!=p.digest || grant.plan_digest!=p.digest || !grant.source_read || !grant.destination_write || !grant.map_write || !grant.host_effects)fail("acquisition_grant");
        const auto& planned=field(p.definition,"resources");V active;Chunk pending;bool has_pending=false,sealed=false,incomplete=false;
        if(resume) {
            ports.open_resume();const auto first=ports.next_record();
            if(first.end || !first.complete)fail("acquisition_map_header");
            const auto header=ledger.accept(first);if(text(field(header,"type"))!="header")fail("acquisition_map_header");
            const auto& h=field(header,"payload");keys(h,{"plan","plan_digest","resources"});
            if(text(field(h,"plan_digest"))!=p.digest || encode(field(h,"plan"))!=encode(p.definition))fail("acquisition_resume_plan");
            active=field(h,"resources");stable_outputs(planned,active,p.bytes);fresh(ports,active);outputs=true;
            for(;;) {
                const auto r=ports.next_record();if(r.end)break;
                if(!r.complete) {incomplete=true;const auto after=ports.next_record();if(!after.end)fail("acquisition_map_truncation");break;}
                if(ledger.sequence>=1048576)fail("acquisition_map_limit");
                const auto v=ledger.accept(r);const auto type=text(field(v,"type"));const auto& payload=field(v,"payload");
                if(sealed)fail("acquisition_map_after_seal");
                if(type=="pending") {
                    if(has_pending)fail("acquisition_map_pending");pending=chunk(payload,p,out.checkpoint_bytes);has_pending=true;out.uncertain_effect=true;
                } else if(type=="checkpoint") {
                    if(!has_pending || encode(payload)!=encode(chunk_value(pending)))fail("acquisition_map_checkpoint");
                    fresh(ports,active);verify(ports,pending,out,false);
                    if(!p.failing_media && !pending.substituted)verify(ports,pending,out,true);
                    out.checkpoint_bytes+=pending.size;if(pending.substituted)out.substituted_bytes+=pending.size;else out.source_bytes+=pending.size;has_pending=false;out.uncertain_effect=false;
                } else if(type=="read_failure") {
                    keys(payload,{"offset","length","read_bytes","retries","read_error"});
                    if(has_pending || out.checkpoint_bytes>=p.bytes || integer(field(payload,"offset"))!=out.checkpoint_bytes ||
                       integer(field(payload,"length"))!=std::min<std::uint64_t>(p.chunk_bytes,p.bytes-out.checkpoint_bytes) ||
                       integer(field(payload,"read_bytes"))>integer(field(payload,"length")) || integer(field(payload,"retries"))>p.retries)fail("acquisition_map_failure");
                    token(field(payload,"read_error"));
                } else if(type=="seal") {
                    keys(payload,{"bytes","source_bytes","substituted_bytes"});
                    if(has_pending || out.checkpoint_bytes!=p.bytes || integer(field(payload,"bytes"))!=p.bytes ||
                       integer(field(payload,"source_bytes"))!=out.source_bytes || integer(field(payload,"substituted_bytes"))!=out.substituted_bytes)fail("acquisition_map_seal");sealed=true;
                } else fail("acquisition_map_record_type");
            }
            fresh(ports,active);
            if(sealed && incomplete)fail("acquisition_map_after_seal");
            if(incomplete)ports.discard_incomplete_tail();
            if(has_pending) {
                out.uncertain_effect=true;
                ledger.require(2);
                // Observe a possibly completed bounded effect before deciding to replay.
                const auto observed=ports.read_destination(pending.offset,pending.size);
                if(observed.error.empty() && observed.bytes.size()==pending.size && hash(observed.bytes)==pending.digest) {
                    if(!p.failing_media && !pending.substituted)verify(ports,pending,out,true);
                    checkpoint(ports,ledger,pending,out,active);has_pending=false;
                } else {
                    if(pending.substituted) {
                        std::vector<unsigned char> zeros(pending.size,0);if(hash(zeros)!=pending.digest)fail("acquisition_map_substitution");
                        fresh(ports,active);ports.write_destination(pending.offset,zeros);out.attempt_written_bytes+=zeros.size();
                    } else {
                        auto r=ports.read_source(pending.offset,pending.size);out.attempt_read_bytes+=r.bytes.size();
                        if(!r.error.empty() || r.bytes.size()!=pending.size || hash(r.bytes)!=pending.digest)fail("acquisition_resume_source_changed");
                        fresh(ports,active);ports.write_destination(pending.offset,r.bytes);out.attempt_written_bytes+=r.bytes.size();
                    }
                    checkpoint(ports,ledger,pending,out,active);has_pending=false;
                }
            }
        } else {
            fresh(ports,planned);if(ports.stop_requested()) {out.status="paused";return out;}
            outputs=true;
            try {active=ports.create_outputs(p);}catch(const CreationRefusal&) {outputs=false;throw;}
            stable_outputs(planned,active,p.bytes);fresh(ports,active);
            ledger.append("header",V::object().put("plan",p.definition).put("plan_digest",V::string(p.digest)).put("resources",active));
        }
        while(out.checkpoint_bytes<p.bytes) {
            fresh(ports,active);if(ports.stop_requested()) {out.status="paused";out.records=ledger.sequence;return out;}
            ledger.require(3); // intent, completion and terminal seal capacity before data I/O
            Chunk c;c.offset=out.checkpoint_bytes;c.size=static_cast<std::uint32_t>(std::min<std::uint64_t>(p.chunk_bytes,p.bytes-c.offset));Read read;
            for(;;) {
                read=ports.read_source(c.offset,c.size);out.attempt_read_bytes+=read.bytes.size();
                if(read.bytes.size()>c.size)fail("acquisition_provider_read_limit");
                c.error=read.error.empty() && read.bytes.size()!=c.size?"short_read":read.error;
                if(!c.error.empty()) {
                    try {token(V::string(c.error));}catch(const Error&) {fail("acquisition_provider_error");}
                }
                if(c.error.empty() || c.retries==p.retries)break;
                ++c.retries;fresh(ports,active);
            }
            c.read_bytes=read.bytes.size();
            if(!c.error.empty()) {
                if(!p.substitute) {
                    fresh(ports,active);
                    ledger.append("read_failure",V::object().put("offset",number(c.offset)).put("length",number(c.size)).put("read_bytes",number(c.read_bytes))
                        .put("retries",number(c.retries)).put("read_error",V::string(c.error)));
                    out.diagnostic="acquisition_source_read";out.records=ledger.sequence;return out;
                }
                read.bytes.assign(c.size,0);c.substituted=true;
            }
            c.digest=hash(read.bytes);fresh(ports,active);ledger.append("pending",chunk_value(c));out.uncertain_effect=true;
            ports.write_destination(c.offset,read.bytes);out.attempt_written_bytes+=read.bytes.size();
            checkpoint(ports,ledger,c,out,active);
        }
        fresh(ports,active);
        if(!sealed)ledger.append("seal",V::object().put("bytes",number(p.bytes)).put("source_bytes",number(out.source_bytes)).put("substituted_bytes",number(out.substituted_bytes)));
        out.status=out.substituted_bytes?"completed_with_substitution":"completed";out.records=ledger.sequence;return out;
    } catch(const std::exception& e) {
        out.status=outputs?"failed":"refused";out.diagnostic=e.what();out.records=ledger.sequence;return out;
    }
}
json::Value Outcome::report() const {
    return V::object().put("schema",V::string("org.disked.acquisition-outcome-prototype/1")).put("status",V::string(status)).put("diagnostic",V::string(diagnostic))
        .put("consistency",V::string("live-uncoordinated")).put("checkpoint_bytes",number(checkpoint_bytes)).put("source_bytes",number(source_bytes))
        .put("substituted_bytes",number(substituted_bytes)).put("attempt_read_bytes",number(attempt_read_bytes)).put("attempt_written_bytes",number(attempt_written_bytes))
        .put("attempt_verified_bytes",number(attempt_verified_bytes)).put("records",number(records)).put("uncertain_effect",V::boolean_value(uncertain_effect));
}
}}
