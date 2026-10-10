#include "operation.h"
#include "sha256.h"
namespace disked { namespace acquisition_operation {
using V=json::Value;
namespace {
[[noreturn]] void reject(const char* code) {throw std::invalid_argument(code);}
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)reject("acquisition_worker_shape");return *p;}
std::string text(const V& v,const char* name) {const auto& p=field(v,name);if(p.kind!=V::Kind::string)reject("acquisition_worker_shape");return p.text;}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())reject("acquisition_worker_shape");for(const auto n:names)field(v,n);
}
void identifier(const std::string& v,const char* prefix,std::size_t length) {
    const std::string p=prefix;if(v.size()!=p.size()+length || v.compare(0,p.size(),p) || v.find_first_not_of("0123456789abcdef",p.size())!=std::string::npos)reject("acquisition_worker_identity");
}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("acquisition_worker_integer");return std::stoull(v.text);}
bool boolean(const V& v) {if(v.kind!=V::Kind::boolean)reject("acquisition_worker_shape");return v.boolean;}
}
std::string hash(const std::string& bytes) {
    unsigned char result[32];sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),result);
    const char* digits="0123456789abcdef";std::string out;for(const auto b:result) {out+=digits[b>>4];out+=digits[b&15];}return out;
}
json::Limits row_limits() {json::Limits l;l.bytes=record_limit;l.depth=20;l.values=2048;l.string_bytes=1024;return l;}
V expected_binding(const V& header) {
    const auto& d=field(header,"definition");
    return V::object().put("operation_id",field(header,"operation_id")).put("worker_epoch",field(header,"worker_epoch")).put("attempt_id",field(header,"attempt_id"))
        .put("definition_digest",field(header,"definition_digest")).put("image_digest",field(d,"image_digest")).put("host_id",field(d,"host_id"))
        .put("capture_epoch",field(field(d,"plan"),"capture_epoch"));
}
void validate_state(const V& state,const V& header,std::size_t sequence) {
    keys(state,{"schema","binding","sequence","phase","checkpoint_bytes","source_bytes","substituted_bytes","observed_filetime","quiescent","outcome","receipt"});
    if(text(state,"schema")!="org.disked.acquisition-worker-state/1" || integer(field(state,"sequence"))!=sequence || !integer(field(state,"observed_filetime")))reject("acquisition_worker_state");
    auto b=field(state,"binding");keys(b,{"operation_id","worker_epoch","attempt_id","definition_digest","image_digest","host_id","capture_epoch","process_id","process_created"});
    const auto pid=integer(field(b,"process_id"));if(!pid || pid>0xffffffffULL || !integer(field(b,"process_created")))reject("acquisition_worker_identity");
    b.fields.erase("process_id");b.fields.erase("process_created");if(json::dump(b)!=json::dump(expected_binding(header)))reject("acquisition_worker_identity");
    const auto total=acquisition::prepare(field(field(header,"definition"),"plan")).bytes;
    const auto covered=integer(field(state,"checkpoint_bytes")),source=integer(field(state,"source_bytes")),zeros=integer(field(state,"substituted_bytes"));
    if(covered>total || source>covered || zeros!=covered-source)reject("acquisition_worker_coverage");
    const auto phase=text(state,"phase");const auto quiescent=boolean(field(state,"quiescent"));
    if(phase=="active") {if(quiescent || field(state,"outcome").kind!=V::Kind::null || field(state,"receipt").kind!=V::Kind::null)reject("acquisition_worker_state");}
    else {
        if(phase!="finished" || !quiescent || field(state,"outcome").kind!=V::Kind::object)reject("acquisition_worker_state");
        const auto& out=field(state,"outcome");
        keys(out,{"schema","status","diagnostic","consistency","checkpoint_bytes","source_bytes","substituted_bytes","attempt_read_bytes","attempt_written_bytes","attempt_verified_bytes","records","uncertain_effect"});
        if(text(out,"schema")!="org.disked.acquisition-outcome-prototype/1" || text(out,"consistency")!="live-uncoordinated" ||
            integer(field(out,"checkpoint_bytes"))!=covered || integer(field(out,"source_bytes"))!=source || integer(field(out,"substituted_bytes"))!=zeros || integer(field(out,"records"))>1048576)reject("acquisition_worker_outcome");
        text(out,"diagnostic");for(const auto name:{"attempt_read_bytes","attempt_written_bytes","attempt_verified_bytes"})integer(field(out,name));
        const auto status=text(out,"status");const auto uncertain=boolean(field(out,"uncertain_effect"));
        if(status=="completed" || status=="completed_with_substitution") {
            if(covered!=total || uncertain || (status=="completed")!=(zeros==0) || field(state,"receipt").kind!=V::Kind::object)reject("acquisition_worker_outcome");
        } else if(status!="failed" && status!="refused" && status!="paused")reject("acquisition_worker_outcome");
    }
}
History read_history(const std::string& raw,const V& header) {
    if(raw.size()>history_limit)reject("acquisition_worker_history_limit");History h;std::size_t start=0;
    while(start<raw.size()) {
        const auto end=raw.find('\n',start);if(end==std::string::npos) {h.complete=false;break;}
        if(end-start>record_limit || h.count>=record_count_limit)reject("acquisition_worker_history_limit");
        const auto bytes=raw.substr(start,end-start);auto row=json::parse(bytes,row_limits());keys(row,{"schema","state","previous","digest"});
        if(text(row,"schema")!="org.disked.acquisition-worker-record/1" || text(row,"previous")!=h.previous || json::dump(row,row_limits())!=bytes)reject("acquisition_worker_history_chain");
        const auto hash_value=text(row,"digest");identifier(hash_value,"",64);row.fields.erase("digest");
        if(hash(json::dump(row,row_limits()))!=hash_value)reject("acquisition_worker_history_chain");
        const auto& state=field(row,"state");validate_state(state,header,h.count+1);
        if(h.count && (text(h.state,"phase")=="finished" || integer(field(state,"checkpoint_bytes"))<integer(field(h.state,"checkpoint_bytes")) ||
            json::dump(field(state,"binding"))!=json::dump(field(h.state,"binding"))))reject("acquisition_worker_history_order");
        row.put("digest",V::string(hash_value));h.records.push_back(row);h.state=state;h.previous=hash_value;++h.count;start=end+1;
    }
    if(!h.count)reject("acquisition_worker_history_empty");return h;
}
void validate_record(const V& record,const V& definition) {
    keys(record,{"schema","state","previous","digest"});json::dump(record,row_limits());
    if(text(record,"schema")!="org.disked.acquisition-worker-record/1")reject("acquisition_worker_history_chain");
    identifier(text(record,"previous"),"",64);identifier(text(record,"digest"),"",64);
    const auto& state=field(record,"state");const auto& binding=field(state,"binding");
    identifier(text(binding,"operation_id"),"image-op:",32);identifier(text(binding,"worker_epoch"),"worker:",32);identifier(text(binding,"attempt_id"),"attempt:",32);
    const auto sequence=integer(field(state,"sequence"));if(!sequence || sequence>record_count_limit)reject("acquisition_worker_state");
    const auto definition_digest="sha256:"+hash(json::dump(definition));
    auto header=V::object().put("operation_id",field(binding,"operation_id")).put("worker_epoch",field(binding,"worker_epoch"))
        .put("attempt_id",field(binding,"attempt_id")).put("definition",definition).put("definition_digest",V::string(definition_digest));
    validate_state(state,header,static_cast<std::size_t>(sequence));
    auto unsigned_record=record;unsigned_record.fields.erase("digest");
    if(hash(json::dump(unsigned_record,row_limits()))!=text(record,"digest"))reject("acquisition_worker_history_chain");
}
}}
