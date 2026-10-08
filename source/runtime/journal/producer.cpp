#include "producer.h"
#include <algorithm>
#include <map>

namespace disked { namespace journal { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void bad(const char* code) {throw DefinitionError(code);}
const V& get(const V& v,const char* k) {const auto p=v.find(k);if(!p)bad("producer_shape");return *p;}
std::string str(const V& v,const char* k) {const auto& x=get(v,k);if(x.kind!=V::Kind::string)bad("producer_string");return x.text;}
std::uint64_t num(const V& v,const char* k) {const auto s=str(v,k);if(!json::decimal_u64(s))bad("producer_integer");return std::stoull(s);}
void keys(const V& v,const std::vector<std::string>& ks) {if(v.kind!=V::Kind::object || v.fields.size()!=ks.size())bad("producer_shape");for(const auto& k:ks)get(v,k.c_str());}
std::string encode(const V& v,std::size_t limit=131072) {json::Limits l;l.bytes=limit;l.string_bytes=limit;l.values=262144;try{return json::dump(v,l);}catch(const json::Error&) {bad("producer_payload_limit");}}
std::string hashed(const std::string& s) {return digest_text(hash(Bytes(s.begin(),s.end())));}
V capture(const V& d) {return V::object().put("observer_id",get(d,"observer_id")).put("capture_epoch",get(d,"capture_epoch")).put("resources",get(d,"resources"));}
void check_frame(const V& f,const std::string& previous,std::uint64_t sequence) {
    keys(f,{"kind","sequence","operation_id","attempt_id","worker_identity","worker_epoch","publisher_identity","publisher_epoch","step_id","data","previous","digest"});
    if(num(f,"sequence")!=sequence || str(f,"previous")!=previous || str(f,"publisher_identity")!="fake:publisher" || !num(f,"publisher_epoch"))bad("producer_fake_chain");
    auto body=V::object();for(const auto& p:f.fields)if(p.first!="digest" && p.first!="previous")body.put(p.first,p.second);
    if(hashed("DiskEd.fake.guard.log/1\n"+previous+encode(body))!=str(f,"digest"))bad("producer_fake_chain");
}
class Memory final:public Source {
    const Bytes& bytes_;
public:
    explicit Memory(const Bytes& b):bytes_(b) {}
    std::uint64_t size() override {return bytes_.size();}
    Bytes read_at(std::uint64_t offset,std::size_t count) override {
        if(count>max_payload || offset>bytes_.size() || count>bytes_.size()-offset)return {};
        return Bytes(bytes_.begin()+static_cast<std::size_t>(offset),bytes_.begin()+static_cast<std::size_t>(offset)+count);
    }
};
struct Converter {
    const Definition& definition;const Bindings& bindings;const PublisherBinding& publisher;
    Digest header_digest,previous{};std::uint64_t record_sequence=0;
    std::map<std::string,std::uint64_t> sequences;
    std::map<std::string,std::string> references;
    std::string admission;
    Converter(const Definition& d,const Bindings& b,const PublisherBinding& p):definition(d),bindings(b),publisher(p) {const auto h=encode_header(b);header_digest=hash(Bytes(h.begin(),h.begin()+160));previous=header_digest;}
    Bytes record(const V& f) {
        const auto kind=num(f,"kind");if(kind<1 || kind>9)bad("producer_kind");const auto& data=get(f,"data");V payload;
        if(kind<=3 || (kind==4 && data.find("schema"))) {
            payload=data;if(kind==4)admission=hashed(encode(payload,max_payload));
        } else if(kind==4) {
            const auto ref=references.find(str(data,"recovery_frame_digest"));if(ref==references.end())bad("producer_recovery_reference");
            payload=V::object().put("schema",V::string("org.disked.journal-checkpoint-admission-prototype/1"))
                .put("id",V::string("fake:checkpoint:"+str(f,"digest").substr(7))).put("plan_digest",V::string(digest_text(definition.digest())))
                .put("basis_admission_digest",get(data,"basis_admission_digest")).put("recovery_record_digest",V::string(ref->second)).put("capture",capture(get(data,"checkpoint")));
            for(const auto k:{"operation_id","attempt_id","worker_identity","worker_epoch"})payload.put(k,get(f,k));
            admission=hashed(encode(payload,max_payload));
        } else {
            V details=V::object();std::string event,name=str(f,"step_id");
            if(kind==5) {event="intention";details.put("capture",capture(data));}
            if(kind==6) {event="verified_completion";details.put("capture",capture(data)).put("target_flush_capture_epoch",get(data,"flush_capture_epoch")).put("qualified_fake_flush",get(data,"qualified_fake_flush"));}
            if(kind==7) {event="cancellation_request";name=str(data,"pending_step");details.put("requested",get(data,"requested"));}
            if(kind==8) {
                event="recovery_observation";if(str(data,"observed")=="terminal")name.clear();details.put("capture",capture(data));
                for(const auto k:{"flush_capture_epoch","qualified_fake_flush","worker_exited","exit_capture_epoch","observed"})details.put(k,get(data,k));
            }
            if(kind==9) {
                event="seal";name.clear();details.put("capture",capture(data));
                for(const auto k:{"worker_exited","exit_capture_epoch","outcome","cancel_acknowledged"})details.put(k,get(data,k));
            }
            payload=V::object().put("schema",V::string("org.disked.journal-effect-prototype/1"))
                .put("id",V::string("fake:event:"+str(f,"digest").substr(7))).put("plan_digest",V::string(digest_text(definition.digest())))
                .put("admission_digest",V::string(admission)).put("sequence",V::string(std::to_string(++sequences[str(f,"attempt_id")])))
                .put("step_id",V::string(name)).put("event",V::string(event)).put("details",details);
            for(const auto k:{"operation_id","attempt_id","worker_identity","worker_epoch"})payload.put(k,get(f,k));
        }
        const auto s=encode(payload,max_payload);Record r;r.kind=static_cast<std::uint16_t>(kind);r.flags=1;r.sequence=++record_sequence;
        r.publisher=publisher.identity;r.publisher_epoch=publisher.epoch;r.previous=previous;r.payload=Bytes(s.begin(),s.end());
        auto bytes=encode_record(header_digest,r);
        // The framing digest includes the header digest, not just the record bytes.
        std::copy(bytes.end()-trailer_bytes,bytes.end(),previous.begin());references[str(f,"digest")]=digest_text(previous);return bytes;
    }
};
}
std::vector<ProducedJournal> produce_model_history(const Definition& d,const V& history,const Bindings& bindings,const PublisherBinding& publisher) {
    if(history.kind!=V::Kind::array || history.items.empty() || history.items.size()>4)bad("producer_generation_limit");
    if(bindings.plan!=d.digest() || bindings.targets!=d.resources_digest() || bindings.providers!=d.providers_digest() || !publisher.epoch || std::all_of(publisher.identity.begin(),publisher.identity.end(),[](unsigned char c){return c==0;}))bad("producer_binding");
    std::vector<ProducedJournal> out;
    for(const auto& generation:history.items) {
        keys(generation,{"events","tail","tail_candidate","stable_entries","digest"});const auto& frames=get(generation,"events");
        if(frames.kind!=V::Kind::array || frames.items.size()>512 || num(generation,"stable_entries")>frames.items.size())bad("producer_entry_limit");
        Converter converter(d,bindings,publisher);ProducedJournal result;result.bytes=encode_header(bindings);
        auto previous=digest_text(d.digest());std::string raw;
        for(std::size_t i=0;i<frames.items.size();++i) {
            const auto& f=frames.items[i];check_frame(f,previous,i+1);previous=str(f,"digest");const auto encoded=encode(f);
            if(encoded.size()+1>1048576+512-raw.size())bad("producer_fake_history");raw+=encoded+"\n";
            const auto bytes=converter.record(f);if(bytes.size()>max_source-result.bytes.size())bad("producer_byte_limit");result.bytes.insert(result.bytes.end(),bytes.begin(),bytes.end());
            if(i<num(generation,"stable_entries"))result.stable_bytes=result.bytes.size();
        }
        const auto tail=str(generation,"tail");if(raw.size()+tail.size()>1048576+512 || hashed(raw+tail)!=str(generation,"digest"))bad("producer_fake_history");
        if(!tail.empty()) {
            const auto& candidate=get(generation,"tail_candidate");check_frame(candidate,previous,frames.items.size()+1);
            const auto encoded=encode(candidate);if(tail!=encoded.substr(0,encoded.size()/2))bad("producer_fake_tail");
            const auto bytes=converter.record(candidate);if(bytes.size()/2>max_source-result.bytes.size())bad("producer_byte_limit");result.bytes.insert(result.bytes.end(),bytes.begin(),bytes.begin()+bytes.size()/2);
        }
        Memory memory(result.bytes);result.inspection=scan_semantics(memory,d,bindings,publisher);out.push_back(std::move(result));
    }return out;
}
}}}
