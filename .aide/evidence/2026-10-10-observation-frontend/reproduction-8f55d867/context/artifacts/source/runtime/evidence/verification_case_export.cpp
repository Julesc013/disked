#include "verification_case_export.h"
namespace disked { namespace evidence { namespace proposal {
namespace {using V=json::Value;
const V& get(const V& v,const char* n) {const auto p=v.find(n);if(!p)throw Error("verification_case_export_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {if(v.kind!=V::Kind::object || v.fields.size()!=names.size())throw Error("verification_case_export_shape");for(const auto n:names)get(v,n);}
std::string text(const V& v,const char* n) {const auto& x=get(v,n);if(x.kind!=V::Kind::string)throw Error("verification_case_export_shape");return x.text;}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))throw Error("verification_case_export_integer");return std::stoull(v.text);}
void hex(const std::string& s,const std::string& prefix,std::size_t n) {if(s.size()!=prefix.size()+n || s.compare(0,prefix.size(),prefix) || s.find_first_not_of("0123456789abcdef",prefix.size())!=s.npos)throw Error("verification_case_export_identity");}
void path(const std::string& s,std::size_t limit=960) {if(s.empty() || s.size()>limit || !json::valid_utf8(s))throw Error("verification_case_export_path");for(unsigned char c:s)if(c<32 || c==127)throw Error("verification_case_export_path");}
std::string encode(const V& v) {return json::dump(v,verification_case_export_limits());}
void generation(const V& v) {keys(v,{"created","file_id","volume_id"});integer(get(v,"created"));integer(get(v,"volume_id"));hex(text(v,"file_id"),"",32);}
void policy(const V& v) {keys(v,{"identifiers","raw_values","interpretations","customer_data"});for(const auto& x:v.fields)if(x.second.kind!=V::Kind::boolean)throw Error("verification_case_export_policy");}
bool same_file(const V& a,const V& b) {return text(a,"file_id")==text(b,"file_id") && text(a,"volume_id")==text(b,"volume_id");}
void sources(const V& v) {
    keys(v,{"case","collection"});validate_case_source(get(v,"case"));validate_verification_collection_source(get(v,"collection"));
    for(const auto& file:get(get(v,"case"),"files").items)if(same_file(get(file,"metadata"),get(get(v,"collection"),"metadata")))throw Error("verification_case_source_alias");
    encode(v);
}
void effect(const V& v) {
    keys(v,{"schema","artifact","resources"});if(text(v,"schema")!="org.disked.report-export-definition-prototype/1")throw Error("verification_case_export_version");
    const auto& a=get(v,"artifact");keys(a,{"bytes","digest","policy","encoding","scope"});
    if(!integer(get(a,"bytes")) || integer(get(a,"bytes"))>1048577 || text(a,"scope")!="recorded-acquisition-verification-support" || text(a,"encoding")!="private-case-json-utf8-lf/1")throw Error("verification_case_export_artifact");
    hex(text(a,"digest"),"sha256:",64);policy(get(a,"policy"));const auto& r=get(v,"resources");keys(r,{"destination","producer"});
    const auto& d=get(r,"destination");const auto& p=get(r,"producer");keys(d,{"identity","epoch","location","access","verification"});keys(p,{"identity","epoch","location","access","digest"});
    for(const auto role:{"destination","producer"}) {const auto& x=get(r,role);path(text(x,"identity"),256);path(text(x,"location"));hex(text(x,"epoch"),"sha256:",64);}
    if(text(d,"access")!="create-write" || text(d,"verification")!="readback-sha256" || text(p,"access")!="read")throw Error("verification_case_export_access");
    hex(text(p,"digest"),"sha256:",64);if(text(d,"identity")==text(p,"identity") || text(d,"location")==text(p,"location"))throw Error("verification_case_output_alias");
    json::dump(v,export_definition_limits());
}
V observed(const std::string& state,std::uint64_t sequence) {return V::object().put("state",V::string(state)).put("check_sequence",V::string(std::to_string(sequence)));}
}
json::Limits verification_case_export_limits() {json::Limits l;l.bytes=65536;l.depth=32;l.values=8192;l.string_bytes=960;return l;}
void validate_verification_collection_source(const V& v) {
    keys(v,{"schema","path","metadata","ancestors","digest","collection_revision","access","scope"});
    if(text(v,"schema")!="org.disked.file-image-verification-collection-source-prototype/1" || text(v,"access")!="read" || text(v,"scope")!="historical-record-retention-only")throw Error("verification_case_collection_profile");
    path(text(v,"path"));hex(text(v,"digest"),"sha256:",64);hex(text(v,"collection_revision"),"sha256:",64);
    const auto& m=get(v,"metadata");keys(m,{"attributes","bytes","changed","created","file_id","hardlinks","volume_id","written"});hex(text(m,"file_id"),"",32);
    for(const auto name:{"attributes","bytes","changed","created","hardlinks","volume_id","written"})integer(get(m,name));
    const auto a=integer(get(m,"attributes")),n=integer(get(m,"bytes"));
    if(a>0xffffffffULL || (a&(0x10ULL|0x400ULL|0x1000ULL|0x40000ULL|0x400000ULL)) || integer(get(m,"hardlinks"))!=1 || !n || n>1048577)throw Error("verification_case_collection_file");
    const auto& parents=get(v,"ancestors");if(parents.kind!=V::Kind::array || parents.items.empty() || parents.items.size()>120)throw Error("verification_case_collection_ancestors");
    for(const auto& p:parents.items)generation(p);encode(v);
}
void validate_verification_case_export_review(const V& v) {
    keys(v,{"schema","report","sources","effect"});if(text(v,"schema")!="org.disked.acquisition-verification-export-definition-prototype/1")throw Error("verification_case_export_version");
    const auto& report=get(v,"report");keys(report,{"revision","case_revision","collection_revision","case_operation_id","collection_id"});
    for(const auto name:{"revision","case_revision","collection_revision"})hex(text(report,name),"sha256:",64);
    hex(text(report,"case_operation_id"),"image-op:",32);hex(text(report,"collection_id"),"collection:",32);const auto& s=get(v,"sources");sources(s);
    if(text(get(s,"case"),"case_revision")!=text(report,"case_revision") || text(get(s,"collection"),"collection_revision")!=text(report,"collection_revision"))throw Error("verification_case_revision_binding");
    effect(get(v,"effect"));const auto destination=text(get(get(get(v,"effect"),"resources"),"destination"),"location");
    if(destination==text(get(s,"collection"),"path"))throw Error("verification_case_output_alias");
    const auto& store=get(get(s,"case"),"store");for(const auto& child:get(store,"children").items)if(destination==text(store,"path")+"\\"+child.text)throw Error("verification_case_output_alias");
    encode(v);
}
VerificationCaseExportDefinition::VerificationCaseExportDefinition(const AcquisitionVerificationReport& report,const V& s,const ExportDefinition& output):effect_(output) {
    sources(s);const auto& acquisition=get(report.view(),"acquisition");const auto& collection=get(get(report.view(),"verification"),"view");
    const auto& selected=get(acquisition,"view");const auto& before=get(selected,"before");const auto& cs=get(s,"case");const auto& files=get(cs,"files");
    const auto raw_request=text(collection,"request_raw"),raw_history=image_collection_bytes(text(collection,"history_hex"));
    if(text(cs,"case_revision")!=text(acquisition,"revision") || encode(get(cs,"store"))!=encode(get(get(before,"definition"),"store")) ||
       text(files.items[0],"digest")!=export_digest(raw_request) || integer(get(get(files.items[0],"metadata"),"bytes"))!=raw_request.size() ||
       text(files.items[1],"digest")!=export_digest(raw_history) || integer(get(get(files.items[1],"metadata"),"bytes"))!=raw_history.size())throw Error("verification_case_original_binding");
    const CollectionRetentionArtifact retained(ImageVerificationCollection::restore(json::dump(collection,image_collection_limits())+'\n'));
    const auto& coll=get(s,"collection");if(text(coll,"digest")!=retained.digest() || integer(get(get(coll,"metadata"),"bytes"))!=retained.bytes().size() ||
       text(coll,"collection_revision")!=text(get(report.view(),"verification"),"revision"))throw Error("verification_case_collection_binding");
    const SupportArtifact artifact(report,get(output.artifact().description(),"policy"));
    if(encode(artifact.description())!=encode(output.artifact().description()) || artifact.bytes()!=output.artifact().bytes())throw Error("verification_case_export_artifact");
    value_=V::object().put("schema",V::string("org.disked.acquisition-verification-export-definition-prototype/1"))
        .put("report",V::object().put("revision",V::string(report.revision())).put("case_revision",get(acquisition,"revision"))
            .put("collection_revision",get(get(report.view(),"verification"),"revision")).put("case_operation_id",get(before,"operation_id")).put("collection_id",get(collection,"collection_id")))
        .put("sources",s).put("effect",output.value());validate_verification_case_export_review(value_);digest_=export_digest(encode(value_));
}
V VerificationCaseExportOutcome::view() const {
    return V::object().put("schema",V::string("org.disked.acquisition-verification-export-outcome-prototype/1"))
        .put("status",V::string(status)).put("diagnostic",diagnostic.empty()?V{}:V::string(diagnostic)).put("source_checks",V::string(std::to_string(checks)))
        .put("source_observations",V::object().put("case",observed(case_state,case_checked)).put("collection",observed(collection_state,collection_checked)))
        .put("output",output.view()).put("scope",V::string("recorded-acquisition-verification-support-export"))
        .put("authenticity",V::string("not_established")).put("custody_authentication",V::string("not_established"))
        .put("current_image_state",V::string("not_established")).put("power_loss_persistence",V::string("not_established"));
}
VerificationCaseExportOutcome execute_verification_case_export(const VerificationCaseExportDefinition& d,const VerificationCaseExportGrant& g,
    const VerificationCaseSourceObservers& ports,const CheckedExportEffect& effect_port) {
    VerificationCaseExportOutcome out;
    if(g.definition_digest!=d.digest() || !g.case_read || !g.collection_read || !g.report_write || !g.host_effects || !ports.acquisition || !ports.collection || !effect_port) {
        out.diagnostic="verification_case_export_grant";out.output.diagnostic=out.diagnostic;return out;
    }
    auto visit=[&](bool collection) {
        if(out.checks==256)throw Error("verification_case_check_limit");
        auto& state=collection?out.collection_state:out.case_state;auto& sequence=collection?out.collection_checked:out.case_checked;
        sequence=++out.checks;state="unresolved";const auto current=collection?ports.collection():ports.acquisition();
        if(collection)validate_verification_collection_source(current);else validate_case_source(current);
        if(encode(current)!=encode(get(get(d.value(),"sources"),collection?"collection":"case"))) {state="changed";throw Error("verification_case_source_changed");}state="matched";
    };
    const auto check=[&] {visit(false);visit(true);};
    try {check();}catch(const std::exception& e) {out.diagnostic=e.what();out.output.diagnostic=out.diagnostic;return out;}
    out.status="unknown";out.output.status="failed";out.output.output_state="uncertain";out.output.uncertain_effect=true;out.output.written_known=false;
    try {out.output=effect_port(ExportGrant{d.effect().digest(),g.report_write,g.host_effects},check);out.status=out.output.status;}
    catch(const std::exception& e) {out.diagnostic=e.what();out.output.diagnostic=out.diagnostic;return out;}
    if(out.status=="completed" && (out.output.phase!="completed" || !out.output.diagnostic.empty() || out.output.output_state!="created" ||
       out.output.flush_state!="api_confirmed" || out.output.uncertain_effect || !out.output.written_known ||
       out.output.submitted!=d.effect().artifact().bytes().size() || out.output.written!=out.output.submitted ||
       out.output.read!=out.output.submitted || out.output.verified!=out.output.submitted)) {
        out.status="unknown";out.diagnostic="verification_case_output_claim";return out;
    }
    try {check();}catch(const std::exception& e) {out.diagnostic=e.what();if(out.status=="completed")out.status="failed";}
    if(out.diagnostic.empty())out.diagnostic=out.output.diagnostic;return out;
}
}}}
