#include "report_operation.h"
namespace disked { namespace report_operation {
using V=json::Value;namespace e=evidence::proposal;
namespace {
[[noreturn]] void reject(const char* code) {throw std::invalid_argument(code);}
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)reject("report_worker_shape");return *p;}
std::string text(const V& v,const char* name) {const auto& p=field(v,name);if(p.kind!=V::Kind::string)reject("report_worker_shape");return p.text;}
void keys(const V& v,std::initializer_list<const char*> names) {
    if(v.kind!=V::Kind::object || v.fields.size()!=names.size())reject("report_worker_shape");for(const auto n:names)field(v,n);
}
void hex(const std::string& value,const char* prefix,std::size_t digits) {
    const std::string p=prefix;if(value.size()!=p.size()+digits || value.compare(0,p.size(),p) || value.find_first_not_of("0123456789abcdef",p.size())!=value.npos)reject("report_worker_identity");
}
std::uint64_t integer(const V& v) {if(v.kind!=V::Kind::string || !json::decimal_u64(v.text))reject("report_worker_integer");return std::stoull(v.text);}
bool boolean(const V& v) {if(v.kind!=V::Kind::boolean)reject("report_worker_shape");return v.boolean;}
bool equal(const V& a,const V& b) {return json::dump(a,definition_limits())==json::dump(b,definition_limits());}
void one(const std::string& v,std::initializer_list<const char*> allowed) {for(const auto a:allowed)if(v==a)return;reject("report_worker_state");}
void nullable_diagnostic(const V& v) {if(v.kind!=V::Kind::null && (v.kind!=V::Kind::string || v.text.size()>256))reject("report_worker_outcome");}
void generation(const V& v) {
    keys(v,{"volume_id","file_id","created"});integer(field(v,"volume_id"));integer(field(v,"created"));hex(text(v,"file_id"),"",32);
}
const V& joint(const V& d) {return field(d,"export");}
const V& artifact(const V& d) {return field(field(joint(d),"effect"),"artifact");}
void outcome(const V& out,const V& definition) {
    keys(out,{"schema","status","source_state","diagnostic","output","scope","authenticity","current_image_verification"});
    if(text(out,"schema")!="org.disked.acquisition-case-export-outcome-prototype/1" || text(out,"scope")!="recorded-acquisition-case-support-export" ||
       text(out,"authenticity")!="not_established" || text(out,"current_image_verification")!="not_performed")reject("report_worker_outcome");
    one(text(out,"status"),{"refused","failed","cancelled","completed","unknown"});one(text(out,"source_state"),{"not_observed","unresolved","matched","changed"});nullable_diagnostic(field(out,"diagnostic"));
    const auto& o=field(out,"output");
    keys(o,{"schema","status","diagnostic","phase","output_state","submitted_bytes","written_bytes","read_bytes","verified_bytes","flush","uncertain_effect","worker_exit","physical_backing_qualified","power_loss_persistence","source_preservation","authenticity"});
    if(text(o,"schema")!="org.disked.report-export-outcome-prototype/1" || text(o,"worker_exit")!="unobserved" || boolean(field(o,"physical_backing_qualified")) ||
       text(o,"power_loss_persistence")!="not_established" || text(o,"source_preservation")!="not_established" || text(o,"authenticity")!="not_established")reject("report_worker_outcome");
    one(text(o,"status"),{"refused","failed","cancelled","completed"});nullable_diagnostic(field(o,"diagnostic"));
    one(text(o,"phase"),{"admission","revalidation","creation","write","flush","readback","verification","completed"});
    one(text(o,"output_state"),{"not_created","uncertain","created"});one(text(o,"flush"),{"not_attempted","uncertain","api_confirmed"});
    const auto size=integer(field(artifact(definition),"bytes"));const auto submitted=integer(field(o,"submitted_bytes")),read=integer(field(o,"read_bytes")),verified=integer(field(o,"verified_bytes"));
    const auto& w=field(o,"written_bytes");const auto known=w.kind!=V::Kind::null;const auto written=known?integer(w):0;
    if(submitted>size || read>size || verified>read || (known && written>submitted))reject("report_worker_counters");
    const auto uncertain=boolean(field(o,"uncertain_effect"));
    if(text(o,"output_state")=="not_created" && (submitted || written || read || verified || !known || uncertain || text(o,"flush")!="not_attempted"))reject("report_worker_counters");
    if(text(o,"status")=="completed" && (!known || uncertain || text(o,"output_state")!="created" || text(o,"flush")!="api_confirmed" ||
       submitted!=size || written!=size || read!=size || verified!=size || text(o,"phase")!="completed"))reject("report_worker_outcome");
    if(text(out,"status")=="completed" && (text(out,"source_state")!="matched" || text(o,"status")!="completed"))reject("report_worker_outcome");
    if(text(out,"status")=="unknown" && (!uncertain || text(o,"output_state")!="uncertain"))reject("report_worker_outcome");
}
void receipt(const V& v,const V& out,const V& definition) {
    if(v.kind==V::Kind::null) {if(text(field(out,"output"),"status")=="completed")reject("report_worker_receipt");return;}
    keys(v,{"definition_digest","output_receipt","routing_metadata_is_support_export"});
    if(text(v,"definition_digest")!=digest(joint(definition)) || boolean(field(v,"routing_metadata_is_support_export")))reject("report_worker_receipt");
    const auto& r=field(v,"output_receipt");const auto& o=field(out,"output");
    if(r.kind==V::Kind::null) {if(text(o,"output_state")!="not_created")reject("report_worker_receipt");return;}
    keys(r,{"definition_digest","artifact_digest","routing_metadata_is_support_export","output_path","output_created_observed","output_metadata","producer","platform_code","flush_scope"});
    const auto& effect=field(joint(definition),"effect");const auto& resources=field(effect,"resources");
    if(text(r,"definition_digest")!=digest(effect) || text(r,"artifact_digest")!=text(artifact(definition),"digest") || boolean(field(r,"routing_metadata_is_support_export")) ||
       text(r,"output_path")!=text(field(resources,"destination"),"location") || !equal(field(r,"producer"),field(resources,"producer")) ||
       integer(field(r,"platform_code"))>0xffffffffULL || text(r,"flush_scope")!="per-file-FlushFileBuffers-API-only")reject("report_worker_receipt");
    const auto created=boolean(field(r,"output_created_observed"));if((text(o,"output_state")=="created" && !created) || (text(o,"output_state")=="not_created" && created))reject("report_worker_receipt");
    const auto& metadata=field(r,"output_metadata");
    if(metadata.kind!=V::Kind::null) {
        if(!created)reject("report_worker_receipt");
        keys(metadata,{"volume_id","file_id","bytes","created","written","changed","attributes","hardlinks"});hex(text(metadata,"file_id"),"",32);
        for(const auto n:{"volume_id","bytes","created","written","changed","attributes","hardlinks"})integer(field(metadata,n));
        const auto attrs=integer(field(metadata,"attributes"));
        if(integer(field(metadata,"hardlinks"))!=1 || integer(field(metadata,"bytes"))>integer(field(artifact(definition),"bytes")) || attrs>0xffffffffULL ||
           attrs&(0x10|0x400|0x1000|0x40000|0x400000))reject("report_worker_receipt");
        if(text(o,"status")=="completed" && integer(field(metadata,"bytes"))!=integer(field(artifact(definition),"bytes")))reject("report_worker_receipt");
    }
}
}
json::Limits definition_limits() {json::Limits l;l.bytes=definition_limit;l.depth=28;l.values=8192;l.string_bytes=1024;return l;}
json::Limits row_limits() {json::Limits l;l.bytes=record_limit;l.depth=28;l.values=8192;l.string_bytes=1024;return l;}
std::string digest(const V& v) {return e::export_digest(json::dump(v,definition_limits()));}
void validate_definition(const V& d) {
    keys(d,{"schema","export","store","host_id","image_digest","source_revision","input_digest","target_profile"});
    if(text(d,"schema")!="org.disked.report-worker-definition-prototype/1" || text(d,"target_profile")!="windows.nt10.x64.win32")reject("report_worker_version");
    e::validate_acquisition_export_review(joint(d));hex(text(d,"host_id"),"",64);hex(text(d,"image_digest"),"",64);hex(text(d,"source_revision"),"",40);hex(text(d,"input_digest"),"sha256:",64);
    if(text(field(field(field(joint(d),"effect"),"resources"),"producer"),"digest")!="sha256:"+text(d,"image_digest"))reject("report_worker_code_binding");
    const auto& s=field(d,"store");keys(s,{"path","generation","ancestors","access","children","failure_domain"});
    const auto path=text(s,"path");if(path.empty() || path.size()>960 || path.find('\0')!=path.npos || text(s,"access")!="create-owned-metadata")reject("report_worker_store");
    generation(field(s,"generation"));const auto& parents=field(s,"ancestors");
    if(parents.kind!=V::Kind::array || parents.items.empty() || parents.items.size()>120)reject("report_worker_store");for(const auto& p:parents.items)generation(p);
    if(!equal(parents.items.back(),field(s,"generation")) || text(s,"failure_domain")!="observed-file-volume:"+text(field(s,"generation"),"volume_id"))reject("report_worker_store");
    const auto& names=field(s,"children");if(names.kind!=V::Kind::array || names.items.size()!=4)reject("report_worker_store");
    std::size_t i=0;for(const auto n:{"report.request","report.records","report.cancel","report.admission"}) {if(names.items[i].kind!=V::Kind::string || names.items[i++].text!=n)reject("report_worker_store");}
    if(equal(field(s,"generation"),field(field(field(joint(d),"source"),"store"),"generation")))reject("report_worker_source_store_alias");
    json::dump(d,definition_limits());
}
void validate_grant(const V& g,const V& d) {
    keys(g,{"definition_digest","case_read","report_write","store_write","host_effects"});
    if(text(g,"definition_digest")!=digest(d))reject("report_worker_grant");
    for(const auto n:{"case_read","report_write","store_write","host_effects"})if(!boolean(field(g,n)))reject("report_worker_grant");
}
void validate_header(const V& h) {
    keys(h,{"schema","operation_id","worker_epoch","attempt_id","definition","definition_digest","grant","records_id","cancel_id"});
    if(text(h,"schema")!="org.disked.report-worker-request-prototype/1" || text(h,"definition_digest")!=digest(field(h,"definition")))reject("report_worker_request");
    hex(text(h,"operation_id"),"report-op:",32);hex(text(h,"worker_epoch"),"worker:",32);hex(text(h,"attempt_id"),"attempt:",32);
    for(const auto n:{"records_id","cancel_id"}) {const auto id=text(h,n);const auto p=id.find(':');if(p==id.npos || !json::decimal_u64(id.substr(0,p)) || !json::decimal_u64(id.substr(p+1)))reject("report_worker_identity");}
    if(text(h,"records_id")==text(h,"cancel_id"))reject("report_worker_identity");validate_definition(field(h,"definition"));validate_grant(field(h,"grant"),field(h,"definition"));json::dump(h,definition_limits());
}
V expected_binding(const V& h) {
    const auto& d=field(h,"definition");return V::object().put("operation_id",field(h,"operation_id")).put("worker_epoch",field(h,"worker_epoch")).put("attempt_id",field(h,"attempt_id"))
        .put("definition_digest",field(h,"definition_digest")).put("image_digest",field(d,"image_digest")).put("host_id",field(d,"host_id"));
}
void validate_state(const V& s,const V& h,std::size_t sequence) {
    keys(s,{"schema","binding","sequence","phase","cancellation","effect_certainty","observed_filetime","quiescent","outcome","receipt"});
    if(text(s,"schema")!="org.disked.report-worker-state-prototype/1" || !sequence || sequence>record_count_limit || integer(field(s,"sequence"))!=sequence || !integer(field(s,"observed_filetime")))reject("report_worker_state");
    auto b=field(s,"binding");keys(b,{"operation_id","worker_epoch","attempt_id","definition_digest","image_digest","host_id","process_id","process_created"});
    if(!integer(field(b,"process_id")) || integer(field(b,"process_id"))>0xffffffffULL || !integer(field(b,"process_created")))reject("report_worker_identity");
    b.fields.erase("process_id");b.fields.erase("process_created");if(!equal(b,expected_binding(h)))reject("report_worker_identity");
    one(text(s,"cancellation"),{"not_requested","observed"});const auto phase=text(s,"phase"),certainty=text(s,"effect_certainty");const auto quiet=boolean(field(s,"quiescent"));
    if(phase=="prepared" || phase=="executing") {
        if(quiet || field(s,"outcome").kind!=V::Kind::null || field(s,"receipt").kind!=V::Kind::null || certainty!=(phase=="prepared"?"not_started":"in_flight"))reject("report_worker_state");
    } else {
        if(phase!="finished" || !quiet)reject("report_worker_state");outcome(field(s,"outcome"),field(h,"definition"));receipt(field(s,"receipt"),field(s,"outcome"),field(h,"definition"));
        const auto uncertain=boolean(field(field(field(s,"outcome"),"output"),"uncertain_effect"));if(certainty!=(uncertain?"uncertain":"observed"))reject("report_worker_state");
    }
    json::dump(s,row_limits());
}
History read_history(const std::string& raw,const V& h) {
    validate_header(h);if(raw.size()>history_limit)reject("report_worker_history_limit");History out;std::size_t start=0;
    while(start<raw.size()) {
        const auto end=raw.find('\n',start);if(end==raw.npos) {out.complete=false;break;}
        if(end-start>record_limit || out.count>=record_count_limit)reject("report_worker_history_limit");
        const auto bytes=raw.substr(start,end-start);auto row=json::parse(bytes,row_limits());keys(row,{"schema","state","previous","digest"});
        if(text(row,"schema")!="org.disked.report-worker-record-prototype/1" || text(row,"previous")!=out.previous || json::dump(row,row_limits())!=bytes)reject("report_worker_history_chain");
        const auto hash=text(row,"digest");hex(hash,"",64);row.fields.erase("digest");if(e::export_digest(json::dump(row,row_limits()))!="sha256:"+hash)reject("report_worker_history_chain");
        const auto& state=field(row,"state");validate_state(state,h,out.count+1);
        if(!out.count && text(state,"phase")!="prepared")reject("report_worker_history_order");
        if(out.count && (text(out.state,"phase")=="finished" || (text(out.state,"phase")=="executing" && text(state,"phase")=="prepared") ||
           (text(out.state,"cancellation")=="observed" && text(state,"cancellation")!="observed") || !equal(field(out.state,"binding"),field(state,"binding"))))reject("report_worker_history_order");
        if(out.count && text(state,"phase")=="prepared")reject("report_worker_history_order");
        if(out.count && text(out.state,"phase")=="prepared" && text(state,"phase")=="finished" &&
           text(field(field(state,"outcome"),"output"),"output_state")!="not_created")reject("report_worker_history_order");
        row.put("digest",V::string(hash));out.records.push_back(row);out.state=state;out.previous=hash;++out.count;start=end+1;
    }
    if(!out.count)reject("report_worker_history_empty");return out;
}
}}
