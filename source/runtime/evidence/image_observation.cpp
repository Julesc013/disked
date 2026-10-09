#include "image_observation.h"
#include "acquisition_export.h"
#include <limits>
namespace disked { namespace evidence { namespace proposal {
namespace {
using V=json::Value;
[[noreturn]] void fail(const char* code) {throw Error(code);}
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)fail("image_observation_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())fail("image_observation_shape");for(const auto name:names)get(v,name);}
std::string text(const V& v) {if(v.kind!=V::Kind::string)fail("image_observation_shape");return v.text;}
std::string encode(const V& v) {return json::dump(v,image_observation_limits());}
bool same(const V& a,const V& b) {return encode(a)==encode(b);}
std::uint64_t integer(const V& v) {const auto s=text(v);if(!json::decimal_u64(s))fail("image_observation_integer");return std::stoull(s);}
void hex(const V& v,const char* prefix,std::size_t size) {const auto s=text(v);const std::string p=prefix;if(s.size()!=p.size()+size || s.compare(0,p.size(),p) || s.find_first_not_of("0123456789abcdef",p.size())!=s.npos)fail("image_observation_identity");}
void token(const V& v,std::size_t bound) {const auto s=text(v);if(s.empty() || s.size()>bound || !json::valid_utf8(s))fail("image_observation_identity");for(unsigned char c:s)if(c<32 || c==127)fail("image_observation_identity");}
void generation(const V& v) {keys(v,{"created","file_id","volume_id"});integer(get(v,"created"));integer(get(v,"volume_id"));hex(get(v,"file_id"),"",32);}
V file_resource(const V& value) {
    keys(value,{"path","metadata","ancestors","access"});token(get(value,"path"),960);if(text(get(value,"access"))!="read")fail("image_observation_access");
    const auto& m=get(value,"metadata");keys(m,{"attributes","bytes","changed","created","file_id","hardlinks","volume_id","written"});hex(get(m,"file_id"),"",32);
    for(const auto name:{"bytes","changed","created","volume_id","written"})integer(get(m,name));
    const auto attrs=integer(get(m,"attributes"));
    if(attrs>0xffffffffULL || (attrs&(0x10ULL|0x400ULL|0x1000ULL|0x40000ULL|0x400000ULL)) || integer(get(m,"hardlinks"))!=1 || integer(get(m,"bytes"))>static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)()))fail("image_observation_file_profile");
    const auto& parents=get(value,"ancestors");if(parents.kind!=V::Kind::array || parents.items.empty() || parents.items.size()>120)fail("image_observation_ancestors");for(const auto& p:parents.items)generation(p);
    auto id=V::object().put("file_id",get(m,"file_id")).put("volume_id",get(m,"volume_id"));
    auto original=id;original.put("created",get(m,"created"));
    return V::object().put("identity",V::string("file:"+export_digest(encode(id)))).put("epoch",V::string(export_digest(encode(value))))
        .put("recorded_epoch",V::string(export_digest(encode(original)))).put("access",V::string("read")).put("bytes",get(m,"bytes"));
}
V image_resources(const V& binding) {
    keys(binding,{"image","map","provenance"});if(text(get(binding,"provenance"))!="observed-held-ordinary-file-resources")fail("image_observation_binding_profile");
    return V::object().put("image",file_resource(get(binding,"image"))).put("map",file_resource(get(binding,"map")));
}
void revalidation(const V& state,const V& before,const V& after,bool image) {
    const auto name=text(state);
    if(name=="unavailable") {if(after.kind!=V::Kind::null)fail("image_observation_revalidation");return;}
    if(name!="passed" && name!="changed")fail("image_observation_revalidation");
    if(image)image_resources(after);else validate_case_source(after);
    if((name=="passed")!=same(before,after))fail("image_observation_revalidation");
}
V code(const V& value) {
    keys(value,{"source_revision","input_digest","configuration_digest","image_digest","target_profile","source_state"});
    hex(get(value,"source_revision"),"",40);for(const auto name:{"input_digest","configuration_digest","image_digest"})hex(get(value,name),"sha256:",64);
    if(text(get(value,"target_profile"))!="windows.nt10.x64.win32")fail("image_observation_target");
    const auto state=text(get(value,"source_state"));if(state!="clean" && state!="dirty" && state!="exported")fail("image_observation_code_state");return value;
}
V clock(const V& value) {
    keys(value,{"domain","started","finished","elapsed_ms"});auto result=value;const auto domain=text(get(value,"domain"));
    if(domain=="unobserved") {for(const auto name:{"started","finished","elapsed_ms"})if(get(value,name).kind!=V::Kind::null)fail("image_observation_clock");result.put("wall_clock_regressed",V{});}
    else if(domain=="windows-filetime-wall") {
        const auto first=integer(get(value,"started")),last=integer(get(value,"finished"));integer(get(value,"elapsed_ms"));if(!first || !last)fail("image_observation_clock");result.put("wall_clock_regressed",V::boolean_value(last<first));
    }else fail("image_observation_clock");return result;
}
void outcome(const VerificationDefinition& d,const VerificationOutcome& o) {
    if(o.status!="matched" && o.status!="mismatch" && o.status!="incomplete" && o.status!="cancelled" && o.status!="refused" && o.status!="unknown")fail("image_observation_status");
    if(o.diagnostic.size()>128 || o.diagnostic.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")!=o.diagnostic.npos)fail("image_observation_diagnostic");
    if(o.records>1048576 || o.consumed_map_bytes>17180917760ULL || o.records>o.consumed_map_bytes/2 || o.covered_bytes!=o.matched_bytes || o.covered_bytes>d.plan.bytes ||
        o.source_bytes>o.covered_bytes || o.substituted_bytes!=o.covered_bytes-o.source_bytes || o.read_bytes<o.matched_bytes)fail("image_observation_counters");
    if(o.before.kind==V::Kind::null && (o.records || o.consumed_map_bytes || o.covered_bytes || o.read_bytes || o.sealed || o.pending))fail("image_observation_unobserved_prefix");
    if(o.sealed && (o.covered_bytes!=d.plan.bytes || o.pending || o.records<2))fail("image_observation_seal");
    if(o.revalidation=="passed") {if(!same(o.before,d.resources) || !same(o.after,d.resources))fail("image_observation_resources");}
    else if(o.revalidation=="changed" || o.revalidation=="unavailable") {if(o.status!="unknown")fail("image_observation_resources");}
    else if(o.revalidation=="not_attempted") {
        if(o.before.kind!=V::Kind::null || o.after.kind!=V::Kind::null || o.records || o.consumed_map_bytes || o.covered_bytes || o.read_bytes || o.sealed || o.pending || (o.status!="refused" && o.status!="unknown"))fail("image_observation_resources");
    }else fail("image_observation_resources");
    if(o.before.kind!=V::Kind::null && !same(o.before,d.resources))fail("image_observation_resources");
    if(o.status=="matched" && (o.revalidation!="passed" || !o.sealed || o.pending || !o.diagnostic.empty() || o.records<2 || o.covered_bytes!=d.plan.bytes ||
        o.consumed_map_bytes!=integer(get(get(d.resources,"map"),"bytes")) || integer(get(get(d.resources,"image"),"bytes"))!=d.plan.bytes))fail("image_observation_match");
}
V claims() {return V::object().put("authenticity",V::string("not_established")).put("source_preservation",V::string("not_established"))
    .put("point_in_time_acquisition",V::string("not_established")).put("latest_image_state",V::string("not_established"))
    .put("worker_exit",V::string("not_observed")).put("physical_admission",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));}
}
json::Limits image_observation_limits() {json::Limits l;l.bytes=262144;l.string_bytes=32768;l.values=32768;l.depth=32;return l;}
V verification_image_resources(const V& v) {return image_resources(v);}
void validate_verifier_code(const V& v) {code(v);}
VerificationOutcome restore_verification_outcome(const VerificationDefinition& d,const V& v) {
    VerificationOutcome o;
    o.status=text(get(v,"status"));o.diagnostic=text(get(v,"diagnostic"));o.revalidation=text(get(v,"resource_revalidation"));o.before=get(v,"before");o.after=get(v,"after");
    o.records=integer(get(v,"records"));o.consumed_map_bytes=integer(get(v,"consumed_map_bytes"));o.covered_bytes=integer(get(v,"covered_bytes"));o.read_bytes=integer(get(v,"read_bytes"));
    o.matched_bytes=integer(get(v,"matched_bytes"));o.source_bytes=integer(get(v,"source_bytes"));o.substituted_bytes=integer(get(v,"substituted_bytes"));
    for(const auto key:{"sealed","pending"})if(get(v,key).kind!=V::Kind::boolean)fail("image_observation_shape");
    o.sealed=get(v,"sealed").boolean;o.pending=get(v,"pending").boolean;if(!same(o.view(),v))fail("image_observation_shape");
    outcome(d,o);return o;
}
ImageVerificationObservation::ImageVerificationObservation(const AcquisitionCase& report,const std::string& raw,const VerificationDefinition& input,const VerificationOutcome& result,const V& context) {
    keys(context,{"verifier","clock","case_before","case_after","case_revalidation","image_before","image_after","image_binding_revalidation"});
    const auto definition=prepare_verification(input.plan,input.resources);
    if(input.digest!=definition.digest || !same(input.value,definition.value))fail("image_observation_definition");
    const auto& before=get(report.view(),"before");const auto& plan=get(get(before,"definition"),"plan");
    if(!same(plan,definition.plan.definition))fail("image_observation_plan");
    const auto& source=get(context,"case_before");validate_case_source(source);const auto& files=get(source,"files");const auto& history=get(report.view(),"history");
    if(text(get(source,"case_revision"))!=report.revision() || !same(get(source,"store"),get(get(before,"definition"),"store")) ||
        text(get(files.items[1],"digest"))!=text(get(history,"raw_digest")) || !same(get(get(files.items[1],"metadata"),"bytes"),get(history,"bytes")))fail("image_observation_case");
    if(raw.empty() || raw.size()>32768 || integer(get(get(files.items[0],"metadata"),"bytes"))!=raw.size() || text(get(files.items[0],"digest"))!=export_digest(raw))fail("image_observation_request");
    auto request_limits=acquisition_operation::row_limits();request_limits.bytes=32768;request_limits.depth=24;request_limits.values=4096;
    if(!same(json::parse(raw,request_limits),before))fail("image_observation_request");
    if(!same(image_resources(get(context,"image_before")),definition.resources))fail("image_observation_binding");
    revalidation(get(context,"case_revalidation"),source,get(context,"case_after"),false);
    revalidation(get(context,"image_binding_revalidation"),get(context,"image_before"),get(context,"image_after"),true);outcome(definition,result);
    const auto case_state=text(get(context,"case_revalidation")),image_state=text(get(context,"image_binding_revalidation"));
    const auto applicable=case_state=="unavailable" || image_state=="unavailable"?"unavailable":case_state=="changed" || image_state=="changed"?"changed":"applicable";
    auto selected=V::object().put("id",get(report.view(),"case_id")).put("revision",V::string(report.revision()))
        .put("operation_id",get(before,"operation_id")).put("attempt_id",get(before,"attempt_id")).put("worker_epoch",get(before,"worker_epoch"));
    view_=V::object().put("schema",V::string("org.disked.image-verification-observation-prototype/1")).put("case",selected)
        .put("request_raw_digest",V::string(export_digest(raw))).put("request_semantic_digest",V::string(export_digest(encode(before))))
        .put("verifier",code(get(context,"verifier"))).put("clock",clock(get(context,"clock"))).put("definition",definition.value).put("definition_digest",V::string(definition.digest))
        .put("outcome",result.view()).put("case_source_before",source).put("case_source_after",get(context,"case_after")).put("case_revalidation",get(context,"case_revalidation"))
        .put("image_binding_before",get(context,"image_before")).put("image_binding_after",get(context,"image_after")).put("image_binding_revalidation",get(context,"image_binding_revalidation"))
        .put("attachment_applicability",V::string(applicable)).put("scope",V::string("recorded-acquired-image-verification")).put("claims",claims());
    revision_=export_digest(encode(view_));
}
ImageVerificationObservation ImageVerificationObservation::restore(const AcquisitionCase& report,const std::string& raw,const V& retained) {
    encode(retained);const auto& d=get(retained,"definition");
    auto definition=prepare_verification(acquisition::prepare(get(d,"plan")),get(d,"resources"));
    definition.value=d;definition.digest=text(get(retained,"definition_digest"));
    const auto o=restore_verification_outcome(definition,get(retained,"outcome"));
    const auto& stored_clock=get(retained,"clock");keys(stored_clock,{"domain","started","finished","elapsed_ms","wall_clock_regressed"});auto timing=V::object();
    for(const auto key:{"domain","started","finished","elapsed_ms"})timing.put(key,get(stored_clock,key));
    auto context=V::object().put("verifier",get(retained,"verifier")).put("clock",timing)
        .put("case_before",get(retained,"case_source_before")).put("case_after",get(retained,"case_source_after")).put("case_revalidation",get(retained,"case_revalidation"))
        .put("image_before",get(retained,"image_binding_before")).put("image_after",get(retained,"image_binding_after")).put("image_binding_revalidation",get(retained,"image_binding_revalidation"));
    ImageVerificationObservation result(report,raw,definition,o,context);if(!same(result.view(),retained))fail("image_observation_retained_mismatch");return result;
}
V ImageVerificationObservation::support(const V& policy) const {
    keys(policy,{"identifiers","raw_values","interpretations","customer_data"});for(const auto& entry:policy.fields)if(entry.second.kind!=V::Kind::boolean)fail("image_observation_policy");
    const auto& observed=get(view_,"outcome");auto summary=V::object().put("recorded_status",get(observed,"status")).put("resource_revalidation",get(observed,"resource_revalidation"))
        .put("sealed",get(observed,"sealed")).put("pending",get(observed,"pending"));
    auto result=V::object().put("schema",V::string("org.disked.image-verification-support-prototype/1")).put("scope",get(view_,"scope")).put("policy",policy)
        .put("verification",summary).put("case_revalidation",get(view_,"case_revalidation")).put("image_binding_revalidation",get(view_,"image_binding_revalidation"))
        .put("attachment_applicability",get(view_,"attachment_applicability")).put("claims",claims());
    if(get(policy,"raw_values").boolean) {
        auto counters=V::object();for(const auto key:{"records","consumed_map_bytes","covered_bytes","read_bytes","matched_bytes","source_bytes","substituted_bytes"})counters.put(key,get(observed,key));
        result.put("counters",counters).put("clock",get(view_,"clock"));
    }
    if(get(policy,"identifiers").boolean) {
        auto identifiers=V::object();for(const auto key:{"id","operation_id","attempt_id","worker_epoch"})identifiers.put(key,get(get(view_,"case"),key));result.put("identifiers",identifiers).put("verifier",get(view_,"verifier"));
    }
    if(get(policy,"interpretations").boolean)result.put("interpretation",V::object().put("kind",V::string("inference")).put("basis",V::string("recorded-verification-observation"))
        .put("result",V::string(text(get(observed,"status"))=="matched" && text(get(view_,"attachment_applicability"))=="applicable"?"matching-observation-bound-to-case":"unqualified")));
    json::dump(result,case_limits());return result;
}
}}}
