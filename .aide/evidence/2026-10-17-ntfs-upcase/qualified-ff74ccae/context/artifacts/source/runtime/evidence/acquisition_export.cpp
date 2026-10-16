#include "acquisition_export.h"
namespace disked { namespace evidence { namespace proposal {
namespace {
using V=json::Value;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw Error("case_export_shape");return *p;}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())throw Error("case_export_shape");for(const auto key:names)field(v,key);
}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw Error("case_export_shape");return p.text;}
void hex(const std::string& s,const std::string& prefix,std::size_t n) {
    if(s.size()!=prefix.size()+n || s.compare(0,prefix.size(),prefix) || s.find_first_not_of("0123456789abcdef",prefix.size())!=s.npos)throw Error("case_export_identity");
}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))throw Error("case_export_integer");return std::stoull(v.text);}
void generation(const V& v) {keys(v,{"created","file_id","volume_id"});integer(field(v,"created"));integer(field(v,"volume_id"));hex(text(v,"file_id"),"",32);}
void path(const std::string& s) {
    if(s.empty() || s.size()>960 || !json::valid_utf8(s))throw Error("case_export_path");
    for(const auto c:s)if(static_cast<unsigned char>(c)<32 || c==127)throw Error("case_export_path");
}
std::string encode(const V& v) {return json::dump(v,acquisition_export_limits());}
}
json::Limits acquisition_export_limits() {json::Limits l;l.bytes=32768;l.depth=24;l.values=4096;l.string_bytes=960;return l;}
void validate_case_source(const V& source) {
    keys(source,{"schema","access","store","ancestors","files","case_revision","provenance","authenticity"});
    if(text(source,"schema")!="org.disked.file-acquisition-case-source-prototype/1" || text(source,"access")!="read" ||
        text(source,"provenance")!="ordinary-file-read-and-record-validation" || text(source,"authenticity")!="not_established")throw Error("case_export_source_profile");
    hex(text(source,"case_revision"),"sha256:",64);const auto& store=field(source,"store");
    keys(store,{"path","generation","children","access","failure_domain"});path(text(store,"path"));generation(field(store,"generation"));
    auto children=V::array();for(const auto child:{"acquisition.request","acquisition.records","acquisition.cancel","acquisition.admission"})children.items.push_back(V::string(child));
    if(text(store,"access")!="create-owned-metadata" || encode(field(store,"children"))!=encode(children) ||
        text(store,"failure_domain")!="observed-file-volume:"+text(field(store,"generation"),"volume_id"))throw Error("case_export_store");
    const auto& ancestors=field(source,"ancestors");
    if(ancestors.kind!=V::Kind::array || ancestors.items.empty() || ancestors.items.size()>120)throw Error("case_export_ancestors");
    for(const auto& ancestor:ancestors.items)generation(ancestor);
    if(encode(ancestors.items.back())!=encode(field(store,"generation")))throw Error("case_export_ancestors");
    const auto& files=field(source,"files");if(files.kind!=V::Kind::array || files.items.size()!=2)throw Error("case_export_files");
    for(std::size_t i=0;i<2;++i) {
        const auto& f=files.items[i];keys(f,{"name","metadata","digest"});
        if(text(f,"name")!=(i?"acquisition.records":"acquisition.request"))throw Error("case_export_files");hex(text(f,"digest"),"sha256:",64);
        const auto& m=field(f,"metadata");keys(m,{"attributes","bytes","changed","created","file_id","hardlinks","volume_id","written"});
        hex(text(m,"file_id"),"",32);for(const auto key:{"bytes","changed","created","volume_id","written"})integer(field(m,key));
        const auto attrs=integer(field(m,"attributes"));
        if(attrs>0xffffffffULL || (attrs&(0x10ULL|0x400ULL|0x1000ULL|0x40000ULL|0x400000ULL)) || integer(field(m,"hardlinks"))!=1 ||
            !integer(field(m,"bytes")) || integer(field(m,"bytes"))>(i?1048576ULL:32768ULL))throw Error("case_export_file_profile");
    }
    encode(source);
}
void validate_acquisition_export_review(const V& value) {
    keys(value,{"schema","case","source","effect"});
    if(text(value,"schema")!="org.disked.acquisition-case-export-definition-prototype/1")throw Error("case_export_version");
    const auto& selected=field(value,"case");keys(selected,{"operation_id","revision"});
    hex(text(selected,"operation_id"),"image-op:",32);hex(text(selected,"revision"),"sha256:",64);
    const auto& source=field(value,"source");validate_case_source(source);
    if(text(source,"case_revision")!=text(selected,"revision"))throw Error("case_export_source_binding");
    const auto& effect=field(value,"effect");keys(effect,{"schema","artifact","resources"});
    if(text(effect,"schema")!="org.disked.report-export-definition-prototype/1")throw Error("case_export_version");
    const auto& artifact=field(effect,"artifact");keys(artifact,{"bytes","digest","policy","encoding","scope"});
    if(!integer(field(artifact,"bytes")) || integer(field(artifact,"bytes"))>1048577 ||
        text(artifact,"encoding")!="private-case-json-utf8-lf/1" || text(artifact,"scope")!="recorded-acquisition-case-support")throw Error("case_export_artifact_binding");
    hex(text(artifact,"digest"),"sha256:",64);const auto& policy=field(artifact,"policy");
    keys(policy,{"identifiers","raw_values","interpretations","customer_data"});for(const auto& p:policy.fields)if(p.second.kind!=V::Kind::boolean)throw Error("case_export_shape");
    const auto& resources=field(effect,"resources");keys(resources,{"destination","producer"});
    for(const auto role:{"destination","producer"}) {
        const auto& resource=field(resources,role);
        if(std::string(role)=="destination")keys(resource,{"identity","epoch","location","access","verification"});
        else keys(resource,{"identity","epoch","location","access","digest"});
        path(text(resource,"identity"));if(text(resource,"identity").size()>256)throw Error("case_export_identity");
        path(text(resource,"location"));hex(text(resource,"epoch"),"sha256:",64);
    }
    const auto& destination=field(resources,"destination");const auto& producer=field(resources,"producer");
    if(text(destination,"access")!="create-write" || text(destination,"verification")!="readback-sha256" || text(producer,"access")!="read")throw Error("case_export_access");
    hex(text(producer,"digest"),"sha256:",64);
    if(text(destination,"identity")==text(producer,"identity") || text(destination,"location")==text(producer,"location"))throw Error("case_export_alias");
    json::dump(effect,export_definition_limits());encode(value);
}
AcquisitionExportDefinition::AcquisitionExportDefinition(const AcquisitionCase& report,const V& source,const ExportDefinition& effect):effect_(effect) {
    validate_case_source(source);
    const auto& view=report.view();const auto& before=field(view,"before");const auto& history=field(view,"history");
    if(text(source,"case_revision")!=report.revision() || encode(field(source,"store"))!=encode(field(field(before,"definition"),"store")) ||
        text(field(source,"files").items[1],"digest")!=text(history,"raw_digest") ||
        text(field(field(source,"files").items[1],"metadata"),"bytes")!=text(history,"bytes"))throw Error("case_export_source_binding");
    const auto& description=effect.artifact().description();const SupportArtifact selected(report,field(description,"policy"));
    if(encode(selected.description())!=encode(description) || selected.bytes()!=effect.artifact().bytes())throw Error("case_export_artifact_binding");
    value_=V::object().put("schema",V::string("org.disked.acquisition-case-export-definition-prototype/1"))
        .put("case",V::object().put("operation_id",field(before,"operation_id")).put("revision",V::string(report.revision())))
        .put("source",source).put("effect",effect.value());validate_acquisition_export_review(value_);digest_=export_digest(encode(value_));
}
V AcquisitionExportOutcome::view() const {
    return V::object().put("schema",V::string("org.disked.acquisition-case-export-outcome-prototype/1"))
        .put("status",V::string(status)).put("source_state",V::string(source_state)).put("diagnostic",diagnostic.empty()?V{}:V::string(diagnostic))
        .put("output",output.view()).put("scope",V::string("recorded-acquisition-case-support-export"))
        .put("authenticity",V::string("not_established")).put("current_image_verification",V::string("not_performed"));
}
AcquisitionExportOutcome execute_acquisition_export(const AcquisitionExportDefinition& d,const AcquisitionExportGrant& g,
    const CaseSourceObserver& observe,const CheckedExportEffect& effect) {
    AcquisitionExportOutcome out;
    if(g.definition_digest!=d.digest() || !g.case_read || !g.report_write || !g.host_effects || !observe || !effect) {
        out.diagnostic="case_export_grant";out.output.diagnostic=out.diagnostic;return out;
    }
    const auto check=[&] {
        out.source_state="unresolved";const auto current=observe();validate_case_source(current);
        if(encode(current)!=encode(field(d.value(),"source"))) {out.source_state="changed";throw Error("case_export_source_changed");}
        out.source_state="matched";
    };
    try {check();}catch(const std::exception& error) {out.diagnostic=error.what();out.output.diagnostic=out.diagnostic;return out;}
    // An executor exception can have effects: keep the unknown output fact.
    out.status="unknown";out.output.status="failed";out.output.output_state="uncertain";out.output.uncertain_effect=true;out.output.written_known=false;
    try {
        out.output=effect(ExportGrant{d.effect().digest(),g.report_write,g.host_effects},check);out.status=out.output.status;
    }catch(const std::exception& error) {out.diagnostic=error.what();out.output.diagnostic=out.diagnostic;return out;}
    // Output verification and source applicability are distinct dimensions.
    // Never erase the exact output counters/receipt on a later source change.
    try {check();}catch(const std::exception& error) {out.diagnostic=error.what();if(out.status=="completed")out.status="failed";}
    if(out.diagnostic.empty())out.diagnostic=out.output.diagnostic;return out;
}
}}}
