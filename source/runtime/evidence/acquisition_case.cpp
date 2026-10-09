#include "acquisition_case.h"
#include <limits>

namespace disked { namespace evidence { namespace proposal {
namespace {
using V=json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw Error("acquisition_case_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw Error("acquisition_case_shape");return p.text;}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())throw Error("acquisition_case_shape");for(const auto name:names)field(v,name);
}
void identity(const std::string& s,const char* prefix,std::size_t size) {
    const std::string p=prefix;if(s.size()!=p.size()+size || s.compare(0,p.size(),p) || s.find_first_not_of("0123456789abcdef",p.size())!=s.npos)throw Error("acquisition_case_identity");
}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))throw Error("acquisition_case_integer");return std::stoull(v.text);}
bool boolean(const V& v) {if(v.kind!=V::Kind::boolean)throw Error("acquisition_case_shape");return v.boolean;}
std::string digest(const std::string& bytes) {return "sha256:"+acquisition_operation::hash(bytes);}
V code(const V& d) {
    return V::object().put("source_revision",field(d,"source_revision")).put("input_digest",field(d,"input_digest"))
        .put("image_digest",V::string("sha256:"+text(d,"image_digest"))).put("target_profile",field(d,"target_profile"))
        .put("configuration_digest",V{}); // The original request did not record it.
}
V claims() {
    return V::object().put("authenticity",V::string("not_established")).put("source_preservation",V::string("not_established"))
        .put("current_image_verification",V::string("not_performed")).put("worker_exit",V::string("not_observed_by_this_case"))
        .put("physical_admission",V::boolean_value(false)).put("power_loss_persistence",V::string("not_established"))
        .put("mutation_authority",V::boolean_value(false));
}
void header_valid(const V& h) {
    keys(h,{"schema","operation_id","worker_epoch","attempt_id","definition","definition_digest","grant","records_id","cancel_id"});
    if(text(h,"schema")!="org.disked.acquisition-worker-request/1")throw Error("acquisition_case_version");
    identity(text(h,"operation_id"),"image-op:",32);identity(text(h,"worker_epoch"),"worker:",32);identity(text(h,"attempt_id"),"attempt:",32);
    const auto& d=field(h,"definition");keys(d,{"schema","request","plan","store","host_id","image_digest","source_revision","input_digest","target_profile"});
    if(text(d,"schema")!="org.disked.acquisition-worker-definition/1" || text(d,"target_profile")!="windows.nt10.x64.win32")throw Error("acquisition_case_version");
    identity(text(d,"host_id"),"",64);identity(text(d,"image_digest"),"",64);identity(text(d,"source_revision"),"",40);identity(text(d,"input_digest"),"sha256:",64);
    const auto plan=acquisition::prepare(field(d,"plan"));const auto& r=field(d,"request");
    keys(r,{"source","destination","map","resume","explicit_options","chunk_bytes","retry_limit","read_policy","substitution"});
    for(const auto key:{"source","destination","map"}) {const auto s=text(r,key);if(s.empty() || s.size()>960 || s.find('\0')!=s.npos || !json::valid_utf8(s))throw Error("acquisition_case_path");}
    boolean(field(r,"resume"));
    if(!boolean(field(r,"explicit_options")) || integer(field(r,"chunk_bytes"))!=plan.chunk_bytes || integer(field(r,"retry_limit"))!=plan.retries ||
        text(r,"read_policy")!=text(plan.definition,"read_policy") || text(r,"substitution")!=text(plan.definition,"substitution"))throw Error("acquisition_case_request_plan");
    const auto& store=field(d,"store");keys(store,{"path","generation","access","children","failure_domain"});
    const auto path=text(store,"path");if(path.empty() || path.size()>960 || path.find('\0')!=path.npos || !json::valid_utf8(path))throw Error("acquisition_case_path");
    const auto& generation=field(store,"generation");keys(generation,{"created","file_id","volume_id"});
    integer(field(generation,"created"));integer(field(generation,"volume_id"));identity(text(generation,"file_id"),"",32);
    auto children=V::array();for(const auto child:{"acquisition.request","acquisition.records","acquisition.cancel","acquisition.admission"})children.items.push_back(V::string(child));
    if(text(store,"access")!="create-owned-metadata" || json::dump(field(store,"children"))!=json::dump(children) ||
        text(store,"failure_domain")!="observed-file-volume:"+text(generation,"volume_id"))throw Error("acquisition_case_store");
    for(const auto key:{"records_id","cancel_id"}) {const auto s=text(h,key);const auto at=s.find(':');
        if(at==s.npos || !json::decimal_u64(s.substr(0,at)) || !json::decimal_u64(s.substr(at+1)))throw Error("acquisition_case_identity");}
    const auto expected=digest(json::dump(d));if(text(h,"definition_digest")!=expected)throw Error("acquisition_case_definition_digest");
    const auto& g=field(h,"grant");keys(g,{"definition_digest","source_read","destination_write","map_write","host_effects"});
    if(text(g,"definition_digest")!=expected)throw Error("acquisition_case_grant");
    for(const auto key:{"source_read","destination_write","map_write","host_effects"})if(!boolean(field(g,key)))throw Error("acquisition_case_grant");
    json::dump(d,acquisition_operation::row_limits());
    auto limits=acquisition_operation::row_limits();limits.bytes=32768;limits.depth=24;limits.values=4096;json::dump(h,limits);
}
}
json::Limits acquisition_case_limits() {auto l=case_limits();l.bytes=2097152;l.values=262144;return l;}
AcquisitionCase::AcquisitionCase(const V& header,const std::string& raw):header_(header) {
    header_valid(header_);history_=acquisition_operation::read_history(raw,header_);
    const auto& first=field(history_.records.front(),"state");
    if(text(first,"phase")!="active" || integer(field(first,"checkpoint_bytes"))!=0)throw Error("acquisition_case_missing_start");
    const bool terminal=history_.complete && text(history_.state,"phase")=="finished";
    auto records=V::array();records.items=history_.records;
    view_=V::object().put("schema",V::string("org.disked.acquisition-case-prototype/1"))
        .put("case_id",V::string("case:"+text(header_,"operation_id").substr(9))).put("code_identity",code(field(header_,"definition")))
        .put("origin",V::string("validated-request-and-history-declarations"))
        .put("collection_state",V::string(!history_.complete?"unresolved":terminal?"closed":"open"))
        .put("before",header_).put("records",records).put("after",terminal?history_.state:V{})
        .put("history",V::object().put("complete",V::boolean_value(history_.complete)).put("bytes",V::string(std::to_string(raw.size())))
            .put("raw_digest",V::string(digest(raw))).put("last_record_digest",V::string("sha256:"+history_.previous)))
        .put("claims",claims());
    revision_=digest(json::dump(view_,acquisition_case_limits()));
}
V AcquisitionCase::support(const V& policy) const {
    keys(policy,{"identifiers","raw_values","interpretations","customer_data"});
    const bool identifiers=boolean(field(policy,"identifiers")),raw=boolean(field(policy,"raw_values")),interpret=boolean(field(policy,"interpretations")),customer=boolean(field(policy,"customer_data"));
    const auto& d=field(header_,"definition");const auto& p=field(d,"plan");
    auto before=V::object().put("phase",V::string("before")).put("kind",V::string("recorded-execution-definition"));
    if(raw)for(const auto key:{"bytes","chunk_bytes","retry_limit","read_policy","substitution"})before.put(key,field(p,key));
    auto after=V{};
    if(field(view_,"after").kind!=V::Kind::null) {
        const auto& out=field(history_.state,"outcome");after=V::object().put("phase",V::string("after"))
            .put("kind",V::string("recorded-worker-outcome")).put("recorded_status",field(out,"status")).put("consistency",field(out,"consistency"))
            .put("uncertain_effect",field(out,"uncertain_effect"));
        if(raw)for(const auto key:{"checkpoint_bytes","source_bytes","substituted_bytes","attempt_read_bytes","attempt_written_bytes","attempt_verified_bytes","records"})after.put(key,field(out,key));
    }
    auto v=V::object().put("schema",V::string("org.disked.acquisition-case-support-prototype/1"))
        .put("scope",V::string("recorded-ordinary-file-acquisition")).put("policy",policy).put("collection_state",field(view_,"collection_state"))
        .put("before",before).put("after",after).put("accepted_records",V::string(std::to_string(history_.count)))
        .put("history_complete",V::boolean_value(history_.complete)).put("original_binding",V::string("omitted")).put("claims",claims());
    if(interpret)v.put("interpretation",V::object().put("kind",V::string("inference")).put("basis",V::string("validated-recorded-worker-statements"))
        .put("current_image_success",V::string("not_established")));
    if(identifiers)v.put("operation_id",field(header_,"operation_id")).put("attempt_id",field(header_,"attempt_id"))
        .put("worker_epoch",field(header_,"worker_epoch")).put("code_identity",code(d));
    if(identifiers && customer && raw) {
        auto paths=V::object();for(const auto key:{"source","destination","map"})paths.put(key,field(field(d,"request"),key));
        v.put("declared_paths",paths);
    }
    json::dump(v,case_limits());return v;
}
}}}
