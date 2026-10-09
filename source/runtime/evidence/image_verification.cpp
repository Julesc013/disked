#include "image_verification.h"
#include "sha256.h"
#include <algorithm>
#include <limits>
namespace disked { namespace evidence { namespace proposal {
namespace {
using V=json::Value;
struct Failure : std::runtime_error {std::string status;Failure(const char* code,const char* state="refused"):std::runtime_error(code),status(state) {}};
[[noreturn]] void fail(const char* code,const char* state="refused") {throw Failure(code,state);}
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)fail("verification_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())fail("verification_shape");for(const auto n:names)get(v,n);}
std::string text(const V& v) {if(v.kind!=V::Kind::string)fail("verification_shape");return v.text;}
std::uint64_t integer(const V& v) {const auto s=text(v);if(!json::decimal_u64(s))fail("verification_integer");return std::stoull(s);}
void token(const V& v) {const auto s=text(v);if(s.empty() || s.size()>256 || !json::valid_utf8(s))fail("verification_identity");for(unsigned char c:s)if(c<32 || c==127)fail("verification_identity");}
V number(std::uint64_t n) {return V::string(std::to_string(n));}
json::Limits row_limits() {json::Limits l;l.bytes=16384;l.depth=10;l.values=512;l.string_bytes=512;return l;}
json::Limits definition_limits() {auto l=row_limits();l.bytes=32768;l.depth=16;l.values=2048;return l;}
std::string encode(const V& v) {return json::dump(v,row_limits());}
std::string hash(const unsigned char* data,std::size_t size) {unsigned char out[32];sha256(data,size,out);const char* hex="0123456789abcdef";std::string s="sha256:";for(auto b:out) {s+=hex[b>>4];s+=hex[b&15];}return s;}
std::string hash(const std::string& bytes) {return hash(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size());}
bool equal(const V& a,const V& b) {return encode(a)==encode(b);}
const std::uint64_t record_limit=1048576,map_limit=record_limit*16385;
void resources(const V& v) {
    keys(v,{"image","map"});
    for(const auto role:{"image","map"}) {
        const auto& r=get(v,role);keys(r,{"identity","epoch","recorded_epoch","access","bytes"});
        for(const auto key:{"identity","epoch","recorded_epoch"})token(get(r,key));
        if(text(get(r,"access"))!="read")fail("verification_access");
        const auto n=integer(get(r,"bytes"));if(n>static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)()) || (std::string(role)=="map" && n>map_limit))fail("verification_size");
    }
    if(text(get(get(v,"image"),"identity"))==text(get(get(v,"map"),"identity")))fail("verification_alias");
}
void active_resources(const V& planned,const V& active,const acquisition::Plan& p) {
    auto value=p.definition;value.put("resources",active);acquisition::prepare(value);
    for(const auto role:{"source","destination","map","host","executable","provider"}) {
        const auto& a=get(active,role);const auto& b=get(planned,role);
        if(std::string(role)!="destination" && std::string(role)!="map") {if(!equal(a,b))fail("verification_recorded_resources");}
        else for(const auto key:{"access","start","end","failure_domain","verification"})if(!equal(get(a,key),get(b,key)))fail("verification_recorded_resources");
    }
}
void capture(const V& v,const acquisition::Plan& p) {
    keys(v,{"clock","started","attempt_id","capture_epoch"});token(get(v,"attempt_id"));
    if(!equal(get(v,"capture_epoch"),get(p.definition,"capture_epoch")))fail("verification_capture_epoch");
    const auto clock=text(get(v,"clock"));
    if(clock=="unobserved") {if(get(v,"started").kind!=V::Kind::null)fail("verification_capture_clock");}
    else if(clock!="windows-filetime-wall" || !integer(get(v,"started")))fail("verification_capture_clock");
}
void chunk(const V& v,const acquisition::Plan& p,std::uint64_t covered) {
    keys(v,{"offset","length","read_bytes","retries","sha256","state","read_error"});
    const auto n=integer(get(v,"length")),read=integer(get(v,"read_bytes"));
    if(covered>=p.bytes || integer(get(v,"offset"))!=covered || n!=std::min<std::uint64_t>(p.chunk_bytes,p.bytes-covered) || read>n || integer(get(v,"retries"))>p.retries)fail("verification_chunk_geometry");
    const auto digest=text(get(v,"sha256"));if(digest.size()!=71 || digest.substr(0,7)!="sha256:" || digest.find_first_not_of("0123456789abcdef",7)!=digest.npos)fail("verification_chunk_digest");
    const auto state=text(get(v,"state"));const auto& error=get(v,"read_error");
    if(state=="read") {if(error.kind!=V::Kind::null || read!=n)fail("verification_chunk_state");}
    else if(state=="substituted") {
        if(!p.substitute)fail("verification_chunk_state");token(error);
        const std::vector<unsigned char> zeros(static_cast<std::size_t>(n),0);
        if(hash(zeros.data(),zeros.size())!=digest)fail("verification_substitution_digest");
    }else fail("verification_chunk_state");
}
V claims() {return V::object().put("source_preservation",V::string("not_established")).put("authenticity",V::string("not_established"))
    .put("point_in_time_acquisition",V::string("not_established")).put("worker_exit",V::string("not_observed"))
    .put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));}
}
VerificationDefinition prepare_verification(const acquisition::Plan& input,const V& observed) {
    VerificationDefinition d;d.plan=acquisition::prepare(input.definition);
    if(input.digest!=d.plan.digest)fail("verification_plan_digest");resources(observed);d.resources=observed;
    d.value=V::object().put("schema",V::string("org.disked.acquired-image-verification-definition-prototype/1"))
        .put("plan",d.plan.definition).put("plan_digest",V::string(d.plan.digest)).put("resources",observed);
    d.digest=hash(json::dump(d.value,definition_limits()));return d;
}
VerificationOutcome verify_image(const VerificationDefinition& input,const VerificationGrant& grant,VerificationPorts& ports) {
    VerificationOutcome out;bool observed=false,changed=false;
    auto fresh=[&]() {auto current=ports.observe();if(!equal(current,input.resources)) {changed=true;out.after=current;out.revalidation="changed";fail("verification_resource_changed","unknown");}return current;};
    try {
        const auto d=prepare_verification(input.plan,input.resources);
        if(d.digest!=input.digest || json::dump(d.value,definition_limits())!=json::dump(input.value,definition_limits()) || grant.definition_digest!=d.digest || !grant.image_read || !grant.map_read)fail("verification_grant");
        out.before=fresh();observed=true;std::string previous="sha256:"+std::string(64,'0');V pending;
        auto accept=[&](const acquisition::Record& r) {
            if(r.end || r.bytes.size()>16384 || out.records>=record_limit)fail("verification_map_limit");
            if(r.bytes.size()+static_cast<std::size_t>(r.complete)>map_limit-out.consumed_map_bytes)fail("verification_map_limit");
            out.consumed_map_bytes+=r.bytes.size()+(r.complete?1:0);
            if(!r.complete) {const auto tail=ports.next_record();if(!tail.end || !tail.bytes.empty())fail("verification_torn_not_tail");fail("verification_torn_map","incomplete");}
            auto row=json::parse(r.bytes,row_limits());keys(row,{"schema","type","sequence","previous","payload"});
            if(text(get(row,"schema"))!="org.disked.acquisition-record-prototype/2" || integer(get(row,"sequence"))!=out.records || text(get(row,"previous"))!=previous)fail("verification_map_chain");
            if(encode(row)!=r.bytes)fail("verification_map_encoding");previous=hash(r.bytes);++out.records;return row;
        };
        if(ports.stop_requested())fail("verification_cancelled","cancelled");
        const auto first=ports.next_record();if(first.end)fail("verification_map_header");const auto header=accept(first);
        if(text(get(header,"type"))!="header")fail("verification_map_header");const auto& h=get(header,"payload");keys(h,{"plan","plan_digest","resources","capture"});
        if(!equal(get(h,"plan"),d.plan.definition) || text(get(h,"plan_digest"))!=d.plan.digest)fail("verification_recorded_plan");
        capture(get(h,"capture"),d.plan);active_resources(get(d.plan.definition,"resources"),get(h,"resources"),d.plan);
        for(const auto role:{"image","map"}) {
            const auto& current=get(d.resources,role);const auto& original=get(get(h,"resources"),std::string(role)=="image"?"destination":"map");
            if(!equal(get(current,"identity"),get(original,"identity")) || !equal(get(current,"recorded_epoch"),get(original,"epoch")))fail("verification_recorded_identity");
        }
        for(;;) {
            fresh();if(ports.stop_requested())fail("verification_cancelled","cancelled");const auto r=ports.next_record();
            if(r.end) {if(!r.complete || !r.bytes.empty())fail("verification_map_end");break;}
            if(out.sealed)fail("verification_after_seal");const auto row=accept(r);const auto type=text(get(row,"type"));const auto& payload=get(row,"payload");
            if(type=="pending") {if(out.pending)fail("verification_pending");chunk(payload,d.plan,out.covered_bytes);pending=payload;out.pending=true;}
            else if(type=="checkpoint") {
                if(!out.pending || !equal(payload,pending))fail("verification_checkpoint");fresh();
                const auto n=static_cast<std::uint32_t>(integer(get(pending,"length")));auto read=ports.read_image(out.covered_bytes,n);
                if(read.bytes.size()>(std::numeric_limits<std::uint64_t>::max)()-out.read_bytes)fail("verification_counter_limit","unknown");
                out.read_bytes+=read.bytes.size();if(read.bytes.size()>n)fail("verification_provider_read_limit","unknown");fresh();
                if(!read.error.empty() || read.bytes.size()!=n)fail("verification_image_read","unknown");
                if(hash(read.bytes.data(),read.bytes.size())!=text(get(pending,"sha256")))fail("verification_image_digest","mismatch");
                out.matched_bytes+=n;out.covered_bytes+=n;
                if(text(get(pending,"state"))=="substituted")out.substituted_bytes+=n;else out.source_bytes+=n;out.pending=false;
            }else if(type=="read_failure") {
                keys(payload,{"offset","length","read_bytes","retries","read_error"});const auto n=integer(get(payload,"length"));
                if(out.pending || out.covered_bytes>=d.plan.bytes || integer(get(payload,"offset"))!=out.covered_bytes || n!=std::min<std::uint64_t>(d.plan.chunk_bytes,d.plan.bytes-out.covered_bytes) || integer(get(payload,"read_bytes"))>n || integer(get(payload,"retries"))>d.plan.retries)fail("verification_read_failure");token(get(payload,"read_error"));
            }else if(type=="seal") {
                keys(payload,{"bytes","source_bytes","substituted_bytes"});
                if(out.pending || out.covered_bytes!=d.plan.bytes || integer(get(payload,"bytes"))!=d.plan.bytes || integer(get(payload,"source_bytes"))!=out.source_bytes || integer(get(payload,"substituted_bytes"))!=out.substituted_bytes)fail("verification_seal");out.sealed=true;
            }else fail("verification_record_type");
        }
        if(out.consumed_map_bytes!=integer(get(get(d.resources,"map"),"bytes")))fail("verification_map_size","unknown");
        if(!out.sealed)fail("verification_missing_seal","incomplete");
        if(integer(get(get(d.resources,"image"),"bytes"))!=d.plan.bytes)fail("verification_image_size","mismatch");out.status="matched";
    }catch(const Failure& error) {out.status=error.status;out.diagnostic=error.what();}
    catch(const json::Error&) {out.status="refused";out.diagnostic="verification_map_json";}
    catch(const acquisition::Error&) {out.status="refused";out.diagnostic="verification_plan";}
    catch(const std::exception&) {out.status="unknown";out.diagnostic="verification_port_unavailable";}
    if(observed) {
        try {out.after=fresh();out.revalidation=changed?"changed":"passed";if(changed) {out.status="unknown";out.diagnostic="verification_resource_changed";}}
        catch(const Failure& error) {out.status=error.status;out.diagnostic=error.what();}
        catch(const std::exception&) {out.status="unknown";out.diagnostic="verification_revalidation_unavailable";out.revalidation="unavailable";}
    }
    return out;
}
V VerificationOutcome::view() const {
    return V::object().put("schema",V::string("org.disked.acquired-image-verification-outcome-prototype/1"))
        .put("status",V::string(status)).put("diagnostic",V::string(diagnostic)).put("resource_revalidation",V::string(revalidation))
        .put("before",before).put("after",after).put("records",number(records)).put("consumed_map_bytes",number(consumed_map_bytes))
        .put("covered_bytes",number(covered_bytes)).put("read_bytes",number(read_bytes)).put("matched_bytes",number(matched_bytes))
        .put("source_bytes",number(source_bytes)).put("substituted_bytes",number(substituted_bytes)).put("sealed",V::boolean_value(sealed)).put("pending",V::boolean_value(pending))
        .put("scope",V::string("current-ordinary-image-matching-recorded-map")).put("claims",claims());
}
}}}
