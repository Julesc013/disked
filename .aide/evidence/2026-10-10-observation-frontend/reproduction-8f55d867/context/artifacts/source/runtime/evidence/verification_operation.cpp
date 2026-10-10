#include "verification_operation.h"
#include "acquisition_export.h"
namespace disked { namespace verification_operation {
namespace {
using V=json::Value;namespace e=evidence::proposal;
[[noreturn]] void reject(const char* code) {throw std::invalid_argument(code);}
const V& get(const V& v,const char* n) {const auto p=v.find(n);if(!p)reject("verification_worker_shape");return *p;}
std::string text(const V& v,const char* n) {const auto& p=get(v,n);if(p.kind!=V::Kind::string)reject("verification_worker_shape");return p.text;}
void keys(const V& v,std::initializer_list<const char*> names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())reject("verification_worker_shape");for(const auto n:names)get(v,n);}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("verification_worker_integer");return std::stoull(v.text);}
bool boolean(const V& v) {if(v.kind!=V::Kind::boolean)reject("verification_worker_shape");return v.boolean;}
void hex(const std::string& s,const char* prefix,std::size_t n) {const std::string p=prefix;if(s.size()!=p.size()+n || s.compare(0,p.size(),p) || s.find_first_not_of("0123456789abcdef",p.size())!=s.npos)reject("verification_worker_identity");}
bool same(const V& a,const V& b) {return json::dump(a,definition_limits())==json::dump(b,definition_limits());}
void token(const std::string& s,std::size_t n) {if(s.empty() || s.size()>n || !json::valid_utf8(s))reject("verification_worker_identity");for(unsigned char c:s)if(c<32 || c==127)reject("verification_worker_identity");}
void generation(const V& v) {keys(v,{"created","file_id","volume_id"});integer(get(v,"created"));integer(get(v,"volume_id"));hex(text(v,"file_id"),"",32);}
void file_id(const std::string& s) {const auto i=s.find(':');if(i==s.npos || !json::decimal_u64(s.substr(0,i)) || !json::decimal_u64(s.substr(i+1)))reject("verification_worker_identity");}
void one(const std::string& s,std::initializer_list<const char*> values) {for(const auto v:values)if(s==v)return;reject("verification_worker_state");}
void diagnostic(const std::string& s) {if(s.size()>128 || s.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")!=s.npos)reject("verification_worker_diagnostic");}
const char* counters[]={"records","consumed_map_bytes","covered_bytes","read_bytes","source_bytes","substituted_bytes"};
void counts(const V& p,const e::VerificationDefinition& d) {
    keys(p,{"records","consumed_map_bytes","covered_bytes","read_bytes","source_bytes","substituted_bytes"});for(const auto n:counters)integer(get(p,n));
    const auto covered=integer(get(p,"covered_bytes")),map=integer(get(p,"consumed_map_bytes")),records=integer(get(p,"records"));
    if(records>1048576 || records>map/2 || map>integer(get(get(d.resources,"map"),"bytes")) || covered>d.plan.bytes ||
       integer(get(p,"read_bytes"))<covered || integer(get(p,"source_bytes"))>covered || integer(get(p,"substituted_bytes"))!=covered-integer(get(p,"source_bytes")))reject("verification_worker_counters");
}
}
json::Limits definition_limits() {json::Limits l;l.bytes=header_limit;l.values=65536;l.depth=48;l.string_bytes=32768;return l;}
json::Limits row_limits() {auto l=definition_limits();l.bytes=record_limit;l.values=8192;return l;}
std::string digest(const V& v) {return e::export_digest(json::dump(v,definition_limits()));}
e::VerificationDefinition verification(const V& d) {
    const auto& value=get(d,"verification");auto v=e::prepare_verification(acquisition::prepare(get(value,"plan")),get(value,"resources"));
    if(!same(v.value,value) || v.digest!=text(d,"verification_digest"))reject("verification_worker_definition_digest");return v;
}
void validate_definition(const V& d) {
    keys(d,{"schema","case_operation_id","case_source","request_raw","verification","verification_digest","image_binding","store","host_id","verifier","worker_image_path"});
    if(text(d,"schema")!="org.disked.verification-worker-definition-prototype/1")reject("verification_worker_version");
    hex(text(d,"case_operation_id"),"image-op:",32);hex(text(d,"host_id"),"",64);e::validate_verifier_code(get(d,"verifier"));token(text(d,"worker_image_path"),960);
    const auto v=verification(d);if(!same(e::verification_image_resources(get(d,"image_binding")),v.resources))reject("verification_worker_image_binding");
    const auto& source=get(d,"case_source");e::validate_case_source(source);const auto raw=text(d,"request_raw");
    auto request_limits=definition_limits();request_limits.bytes=32768;const auto h=json::parse(raw,request_limits);e::validate_acquisition_case_request(h);
    const auto& files=get(source,"files");if(text(h,"operation_id")!=text(d,"case_operation_id") || !same(get(get(h,"definition"),"plan"),v.plan.definition) ||
       !same(get(get(h,"definition"),"store"),get(source,"store")) || text(files.items[0],"digest")!=e::export_digest(raw) || integer(get(get(files.items[0],"metadata"),"bytes"))!=raw.size())reject("verification_worker_case_binding");
    const auto& s=get(d,"store");keys(s,{"path","generation","ancestors","access","children","failure_domain"});token(text(s,"path"),960);generation(get(s,"generation"));
    if(text(s,"access")!="create-owned-private-metadata" || text(s,"failure_domain")!="observed-file-volume:"+text(get(s,"generation"),"volume_id"))reject("verification_worker_store");
    const auto& parents=get(s,"ancestors");if(parents.kind!=V::Kind::array || parents.items.empty() || parents.items.size()>120)reject("verification_worker_store");for(const auto& p:parents.items)generation(p);
    if(!same(parents.items.back(),get(s,"generation")) || same(get(s,"generation"),get(get(source,"store"),"generation")))reject("verification_worker_store_alias");
    const auto& names=get(s,"children");if(names.kind!=V::Kind::array || names.items.size()!=5)reject("verification_worker_store");std::size_t i=0;
    for(const auto n:{"verification.request","verification.records","verification.cancel","verification.admission","verification.collection"})if(names.items[i].kind!=V::Kind::string || names.items[i++].text!=n)reject("verification_worker_store");
    for(const auto role:{"image","map"}) {
        const auto& f=get(get(d,"image_binding"),role);const auto& ancestors=get(f,"ancestors");
        if(same(ancestors.items.back(),get(s,"generation"))) {
            const auto path=text(f,"path"),leaf=path.substr(path.find_last_of('\\')+1);std::string lower=leaf;for(auto& c:lower)if(c>='A' && c<='Z')c=static_cast<char>(c-'A'+'a');
            for(const auto& n:names.items)if(lower==n.text)reject("verification_worker_store_alias");
        }
    }
    auto limits=definition_limits();limits.bytes=definition_limit;json::dump(d,limits);
}
void validate_grant(const V& g,const V& d) {
    keys(g,{"definition_digest","case_read","image_read","map_read","store_write","host_effects","private_metadata"});if(text(g,"definition_digest")!=digest(d))reject("verification_worker_grant");
    for(const auto n:{"case_read","image_read","map_read","store_write","host_effects","private_metadata"})if(!boolean(get(g,n)))reject("verification_worker_grant");
}
void validate_header(const V& h) {
    keys(h,{"schema","operation_id","attempt_id","worker_epoch","capture_epoch","definition","definition_digest","grant","records_id","cancel_id","collection_id"});
    if(text(h,"schema")!="org.disked.verification-worker-request-prototype/1")reject("verification_worker_version");
    for(const auto n:{"operation_id","attempt_id","worker_epoch","capture_epoch"}) {const char* prefix=std::string(n)=="operation_id"?"verify-op:":std::string(n)=="attempt_id"?"attempt:":std::string(n)=="worker_epoch"?"worker:":"capture:";hex(text(h,n),prefix,32);}
    validate_definition(get(h,"definition"));if(text(h,"definition_digest")!=digest(get(h,"definition")))reject("verification_worker_definition_digest");validate_grant(get(h,"grant"),get(h,"definition"));
    for(const auto n:{"records_id","cancel_id","collection_id"})file_id(text(h,n));
    if(text(h,"records_id")==text(h,"cancel_id") || text(h,"records_id")==text(h,"collection_id") || text(h,"cancel_id")==text(h,"collection_id"))reject("verification_worker_identity");json::dump(h,definition_limits());
}
V expected_binding(const V& h) {
    auto b=V::object();for(const auto n:{"operation_id","attempt_id","worker_epoch","capture_epoch","definition_digest"})b.put(n,get(h,n));
    return b.put("host_id",get(get(h,"definition"),"host_id")).put("verifier",get(get(h,"definition"),"verifier"));
}
void validate_state(const V& s,const V& h,std::size_t sequence) {
    keys(s,{"schema","binding","sequence","phase","cancellation_observation","observed_filetime","quiescent","disposition","progress","outcome","retention","diagnostic"});
    if(text(s,"schema")!="org.disked.verification-worker-state-prototype/1" || !sequence || sequence>record_count_limit || integer(get(s,"sequence"))!=sequence || !integer(get(s,"observed_filetime")))reject("verification_worker_sequence");
    auto b=expected_binding(h);const auto& binding=get(s,"binding");keys(binding,{"operation_id","attempt_id","worker_epoch","capture_epoch","definition_digest","host_id","verifier","process_id","process_created"});
    const auto pid=integer(get(binding,"process_id"));if(!pid || pid>0xffffffffULL || !integer(get(binding,"process_created")))reject("verification_worker_identity");b.put("process_id",get(binding,"process_id")).put("process_created",get(binding,"process_created"));if(!same(b,binding))reject("verification_worker_binding");
    const auto phase=text(s,"phase");one(phase,{"prepared","verifying","persisting","finished"});one(text(s,"cancellation_observation"),{"not_observed","observed"});diagnostic(text(s,"diagnostic"));
    if(boolean(get(s,"quiescent"))!=(phase=="finished"))reject("verification_worker_quiescence");
    const auto d=verification(get(h,"definition"));counts(get(s,"progress"),d);const auto& p=get(s,"progress");
    if(phase=="prepared")for(const auto n:counters)if(integer(get(p,n)))reject("verification_worker_counters");
    const auto& o=get(s,"outcome");if(o.kind!=V::Kind::null) {
        e::restore_verification_outcome(d,o);
        for(const auto name:{"before","after"})if(get(o,name).kind!=V::Kind::null) {
            const auto& resources=get(o,name);e::prepare_verification(d.plan,resources);
            for(const auto role:{"image","map"}) {const auto& resource=get(resources,role);
                hex(text(resource,"identity"),"file:sha256:",64);hex(text(resource,"epoch"),"sha256:",64);hex(text(resource,"recorded_epoch"),"sha256:",64);
            }
        }
        if(text(o,"resource_revalidation")=="unavailable" && get(o,"after").kind!=V::Kind::null)reject("verification_worker_resources");
        if(text(o,"resource_revalidation")=="changed" && (get(o,"after").kind==V::Kind::null || same(get(o,"before"),get(o,"after"))))reject("verification_worker_resources");
        for(const auto n:counters)if(!same(get(o,n),get(p,n)))reject("verification_worker_counters");
    }
    if((phase=="prepared" || phase=="verifying") && o.kind!=V::Kind::null)reject("verification_worker_outcome");
    const auto& retention=get(s,"retention");keys(retention,{"state","bytes","digest","collection_revision","observation_revision","flush"});const auto state=text(retention,"state");one(state,{"empty","in_flight","verified","uncertain"});
    const auto& bytes=get(retention,"bytes");if(bytes.kind!=V::Kind::null && integer(bytes)>1048577)reject("verification_worker_retention");
    for(const auto n:{"digest","collection_revision","observation_revision"})if(get(retention,n).kind!=V::Kind::null)hex(text(retention,n),"sha256:",64);
    one(text(retention,"flush"),{"not_attempted","uncertain","api_confirmed"});
    if(state=="empty") {if(integer(bytes) || text(retention,"flush")!="not_attempted")reject("verification_worker_retention");for(const auto n:{"digest","collection_revision","observation_revision"})if(get(retention,n).kind!=V::Kind::null)reject("verification_worker_retention");}
    if((phase=="prepared" || phase=="verifying") && state!="empty")reject("verification_worker_retention");
    if(phase=="persisting" && (state!="in_flight" || o.kind==V::Kind::null))reject("verification_worker_retention");
    if(state=="verified") {if(phase!="finished" || o.kind==V::Kind::null || bytes.kind==V::Kind::null || !integer(bytes) || text(retention,"flush")!="api_confirmed")reject("verification_worker_retention");for(const auto n:{"digest","collection_revision","observation_revision"})if(get(retention,n).kind==V::Kind::null)reject("verification_worker_retention");}
    if(phase=="finished") {
        if(state=="in_flight" || (o.kind!=V::Kind::null && state=="empty"))reject("verification_worker_retention");
        one(text(s,"disposition"),{"completed","cancelled","refused","unknown"});
        if(text(s,"disposition")=="completed" && (o.kind==V::Kind::null || state!="verified" || text(o,"status")=="cancelled" || text(o,"status")=="unknown"))reject("verification_worker_outcome");
        if(text(s,"disposition")=="cancelled" && (text(s,"cancellation_observation")!="observed" || (o.kind!=V::Kind::null && text(o,"status")!="cancelled")))reject("verification_worker_outcome");
    }else if(text(s,"disposition")!="running")reject("verification_worker_state");
}
void validate_progress(const V& a,const V& b) {
    if(!same(get(a,"binding"),get(b,"binding")) || text(a,"phase")=="finished" || (text(a,"cancellation_observation")=="observed" && text(b,"cancellation_observation")!="observed"))reject("verification_worker_progress");
    const auto rank=[](const std::string& s) {return s=="prepared"?0:s=="verifying"?1:s=="persisting"?2:3;};if(rank(text(b,"phase"))<rank(text(a,"phase")))reject("verification_worker_progress");
    for(const auto n:counters)if(integer(get(get(b,"progress"),n))<integer(get(get(a,"progress"),n)))reject("verification_worker_progress");
    if(text(a,"phase")=="persisting" && (!same(get(a,"outcome"),get(b,"outcome")) || text(b,"phase")!="finished"))reject("verification_worker_progress");
}
void validate_observation(const V& s,const V& d,const std::string& operation) {
    validate_definition(d);hex(operation,"verify-op:",32);const auto& b=get(s,"binding");
    hex(text(b,"attempt_id"),"attempt:",32);hex(text(b,"worker_epoch"),"worker:",32);hex(text(b,"capture_epoch"),"capture:",32);
    // A comparison environment only; never a synthesized persisted header,
    // grant, native file identity or history receipt.
    const auto h=V::object().put("definition",d).put("definition_digest",V::string(digest(d))).put("operation_id",V::string(operation))
        .put("attempt_id",get(b,"attempt_id")).put("worker_epoch",get(b,"worker_epoch")).put("capture_epoch",get(b,"capture_epoch"));
    const auto n=integer(get(s,"sequence"));if(n>record_count_limit)reject("verification_worker_sequence");validate_state(s,h,static_cast<std::size_t>(n));
}
void validate_record(const V& row,const V& h) {
    keys(row,{"schema","state","previous","digest"});if(text(row,"schema")!="org.disked.verification-worker-record-prototype/1")reject("verification_worker_chain");
    hex(text(row,"previous"),"",64);hex(text(row,"digest"),"",64);auto unsigned_row=row;unsigned_row.fields.erase("digest");
    if(acquisition_operation::hash(json::dump(unsigned_row,row_limits()))!=text(row,"digest"))reject("verification_worker_chain");
    const auto n=integer(get(get(row,"state"),"sequence"));if(n>record_count_limit)reject("verification_worker_sequence");validate_state(get(row,"state"),h,static_cast<std::size_t>(n));
    if(n==1 && (text(get(row,"state"),"phase")!="prepared" || text(row,"previous")!=std::string(64,'0')))reject("verification_worker_missing_start");json::dump(row,row_limits());
}
History read_history(const std::string& bytes,const V& h) {
    validate_header(h);if(bytes.size()>history_limit)reject("verification_worker_history_limit");History history;std::size_t offset=0;
    while(offset<bytes.size()) {
        const auto end=bytes.find('\n',offset);if(end==bytes.npos) {if(bytes.size()-offset>record_limit)reject("verification_worker_history_limit");history.complete=false;break;}
        if(end-offset>record_limit || history.count>=record_count_limit)reject("verification_worker_history_limit");const auto raw=bytes.substr(offset,end-offset);const auto row=json::parse(raw,row_limits());
        validate_record(row,h);if(json::dump(row,row_limits())!=raw || text(row,"previous")!=history.previous)reject("verification_worker_chain");const auto hash=text(row,"digest");
        validate_state(get(row,"state"),h,history.count+1);if(history.count)validate_progress(history.state,get(row,"state"));else if(text(get(row,"state"),"phase")!="prepared")reject("verification_worker_missing_start");
        history.state=get(row,"state");history.records.push_back(row);history.previous=hash;++history.count;offset=end+1;
    }
    if(!history.count)reject("verification_worker_missing_start");return history;
}
}}
