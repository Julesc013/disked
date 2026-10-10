#include "image_collection.h"
#include "report_export.h"
namespace disked { namespace evidence { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code) {throw Error(code);}
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)fail("image_collection_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())fail("image_collection_shape");for(const auto key:names)get(v,key);}
std::string text(const V& v) {if(v.kind!=V::Kind::string)fail("image_collection_shape");return v.text;}
std::string encode(const V& v) {return json::dump(v,image_collection_limits());}
void id(const V& v,const char* prefix) {const auto s=text(v);const std::string p=prefix;if(s.size()!=p.size()+32 || s.compare(0,p.size(),p) || s.find_first_not_of("0123456789abcdef",p.size())!=s.npos)fail("image_collection_identity");}
void observer(const V& v) {
    keys(v,{"attempt_id","worker_epoch","capture_epoch","process_id","process_created"});id(get(v,"attempt_id"),"attempt:");id(get(v,"worker_epoch"),"worker:");id(get(v,"capture_epoch"),"capture:");
    for(const auto key:{"process_id","process_created"}) {const auto s=text(get(v,key));if(!json::decimal_u64(s) || !std::stoull(s))fail("image_collection_process");}
    if(std::stoull(text(get(v,"process_id")))>0xffffffffULL)fail("image_collection_process");
}
V process(const V& v) {return V::object().put("worker_epoch",get(v,"worker_epoch")).put("process_id",get(v,"process_id")).put("process_created",get(v,"process_created"));}
V policy(unsigned mask) {auto p=V::object();unsigned bit=1;for(const auto key:{"identifiers","raw_values","interpretations","customer_data"}) {p.put(key,V::boolean_value((mask&bit)!=0));bit<<=1;}return p;}
V claims() {return V::object().put("authenticity",V::string("not_established")).put("custody_authentication",V::string("not_established"))
    .put("latest_image_state",V::string("not_established")).put("worker_exit",V::string("not_observed"))
    .put("power_loss_persistence",V::string("not_established")).put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));}
json::Limits request_limits() {auto l=acquisition_operation::row_limits();l.bytes=32768;l.depth=24;l.values=4096;return l;}
}
json::Limits image_collection_limits() {json::Limits l;l.bytes=1048576;l.string_bytes=1048576;l.values=131072;l.depth=48;return l;}
std::string image_collection_hex(const std::string& bytes) {
    if(bytes.size()>1048576)fail("image_collection_input_limit");const char* digits="0123456789abcdef";std::string result;result.reserve(bytes.size()*2);
    for(unsigned char c:bytes) {result+=digits[c>>4];result+=digits[c&15];}return result;
}
std::string image_collection_bytes(const std::string& hex) {
    if(hex.size()>2097152 || hex.size()%2 || hex.find_first_not_of("0123456789abcdef")!=hex.npos)fail("image_collection_history_encoding");
    std::string result;result.reserve(hex.size()/2);auto nibble=[](char c) {return c>='a'?c-'a'+10:c-'0';};
    for(std::size_t n=0;n<hex.size();n+=2)result+=static_cast<char>((nibble(hex[n])<<4)|nibble(hex[n+1]));return result;
}
ImageVerificationCollection::ImageVerificationCollection(const std::string& collection_id,const AcquisitionCase& report,const std::string& request,const std::string& history):original_(report),request_(request),history_(history),id_(collection_id) {
    id(V::string(id_),"collection:");if(request.empty() || request.size()>32768 || history.size()>1048576)fail("image_collection_input_limit");
    const AcquisitionCase rebuilt(json::parse(request,request_limits()),history);
    if(rebuilt.revision()!=original_.revision() || json::dump(rebuilt.view(),acquisition_case_limits())!=json::dump(original_.view(),acquisition_case_limits()))fail("image_collection_original_mismatch");
    context_=export_digest(encode(V::object().put("collection_id",V::string(id_)).put("case_revision",V::string(original_.revision()))
        .put("request_digest",V::string(export_digest(request_))).put("history_digest",V::string(export_digest(history_)))));refresh();
}
V ImageVerificationCollection::full() const {
    auto records=V::array();for(const auto& entry:entries_)records.items.push_back(entry.record);
    return V::object().put("schema",V::string("org.disked.image-verification-collection-prototype/1")).put("collection_id",V::string(id_))
        .put("case_revision",V::string(original_.revision())).put("request_raw",V::string(request_)).put("history_hex",V::string(image_collection_hex(history_))).put("original_case",original_.view())
        .put("context_digest",V::string(context_)).put("records",records).put("claims",claims());
}
void ImageVerificationCollection::refresh() {auto view=full();const auto revision=export_digest(encode(view));for(unsigned n=0;n<16;++n)json::dump(support(policy(n)),case_limits());view_=std::move(view);revision_=revision;}
ImageVerificationCollection ImageVerificationCollection::with_observation(const ImageVerificationObservation& input,const V& binding) const {
    if(entries_.size()>=16)fail("image_collection_record_limit");observer(binding);
    const auto observation=ImageVerificationObservation::restore(original_,request_,input.view());
    if(observation.revision()!=input.revision())fail("image_collection_observation_identity");
    for(const auto& entry:entries_) {
        if(entry.observation.revision()==input.revision() || text(get(entry.observer,"capture_epoch"))==text(get(binding,"capture_epoch")))fail("image_collection_duplicate");
        if(text(get(entry.observer,"attempt_id"))==text(get(binding,"attempt_id")) && encode(process(entry.observer))!=encode(process(binding)))fail("image_collection_attempt_binding");
        if(text(get(entry.observer,"worker_epoch"))==text(get(binding,"worker_epoch")) && encode(process(entry.observer))!=encode(process(binding)))fail("image_collection_worker_binding");
        if(text(get(entry.observer,"worker_epoch"))==text(get(binding,"worker_epoch")) && encode(get(entry.observation.view(),"verifier"))!=encode(get(observation.view(),"verifier")))fail("image_collection_worker_code_binding");
    }
    auto record=V::object().put("sequence",V::string(std::to_string(entries_.size()+1))).put("observer",binding).put("context_digest",V::string(context_))
        .put("observation_revision",V::string(observation.revision())).put("observation",observation.view())
        .put("previous_digest",entries_.empty()?V::string("sha256:"+std::string(64,'0')):get(entries_.back().record,"digest"));
    record.put("digest",V::string(export_digest(encode(record))));auto next=*this;next.entries_.push_back({observation,binding,record});next.refresh();return next;
}
ImageVerificationCollection ImageVerificationCollection::restore(const std::string& bytes) {
    if(bytes.empty() || bytes.size()>1048577 || bytes.back()!='\n')fail("image_collection_retention_limit");const auto body=bytes.substr(0,bytes.size()-1);
    const auto value=json::parse(body,image_collection_limits());keys(value,{"schema","collection_id","case_revision","request_raw","history_hex","original_case","context_digest","records","claims"});
    if(text(get(value,"schema"))!="org.disked.image-verification-collection-prototype/1")fail("image_collection_version");
    const auto raw=text(get(value,"request_raw")),history=image_collection_bytes(text(get(value,"history_hex")));const AcquisitionCase original(json::parse(raw,request_limits()),history);
    ImageVerificationCollection result(text(get(value,"collection_id")),original,raw,history);const auto& records=get(value,"records");
    if(records.kind!=V::Kind::array || records.items.size()>16)fail("image_collection_record_limit");
    for(const auto& row:records.items) {
        keys(row,{"sequence","observer","context_digest","observation_revision","observation","previous_digest","digest"});
        const auto observation=ImageVerificationObservation::restore(original,raw,get(row,"observation"));auto next=result.with_observation(observation,get(row,"observer"));
        if(encode(next.entries_.back().record)!=encode(row))fail("image_collection_record_mismatch");result=std::move(next);
    }
    if(encode(result.view())!=body)fail("image_collection_retained_mismatch");return result;
}
V ImageVerificationCollection::support(const V& selected) const {
    keys(selected,{"identifiers","raw_values","interpretations","customer_data"});for(const auto& item:selected.fields)if(item.second.kind!=V::Kind::boolean)fail("image_collection_policy");
    auto records=V::array();for(const auto& entry:entries_) {auto row=V::object().put("sequence",get(entry.record,"sequence")).put("observation",entry.observation.support(selected));
        if(get(selected,"identifiers").boolean)row.put("observer",entry.observer);records.items.push_back(row);}
    auto value=V::object().put("schema",V::string("org.disked.image-verification-collection-support-prototype/1")).put("scope",V::string("recorded-image-verification-collection"))
        .put("policy",selected).put("records",records).put("original_case_claims",get(original_.view(),"claims")).put("claims",claims());
    if(get(selected,"identifiers").boolean)value.put("collection_id",V::string(id_));json::dump(value,case_limits());return value;
}
CollectionRetentionArtifact::CollectionRetentionArtifact(const ImageVerificationCollection& report) {
    bytes_=encode(report.view())+'\n';if(bytes_.size()>1048577)fail("image_collection_retention_limit");digest_=export_digest(bytes_);
    description_=V::object().put("bytes",V::string(std::to_string(bytes_.size()))).put("digest",V::string(digest_)).put("policy",V{})
        .put("encoding",V::string("private-image-verification-collection-json-utf8-lf/1")).put("scope",V::string("recorded-image-verification-collection-private"));
}
}}}
