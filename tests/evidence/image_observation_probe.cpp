#include "image_observation.h"
#include "acquisition_export.h"
#include "file_case.h"
#include "file_verification.h"
#include "file_export.h"
#include "worker_files.h"
#include "bootstrap_registry.h"
#include <cstdio>
#include <cstring>
namespace e=disked::evidence::proposal;using V=disked::json::Value;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("observation_probe_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& value=get(v,key);if(value.kind!=V::Kind::string)throw e::Error("observation_probe_shape");return value.text;}
std::uint64_t integer(const V& v,const char* key) {const auto s=text(v,key);if(!disked::json::decimal_u64(s))throw e::Error("observation_probe_integer");return std::stoull(s);}
bool flag(const V& v,const char* key) {const auto& value=get(v,key);if(value.kind!=V::Kind::boolean)throw e::Error("observation_probe_shape");return value.boolean;}
disked::json::Limits limits() {auto l=e::image_observation_limits();l.bytes=4194304;l.string_bytes=2097152;l.values=262144;return l;}
std::string read(bool line,std::size_t bound) {std::string s;for(int c=std::getchar();c!=EOF && (!line || c!='\n');c=std::getchar()) {s+=static_cast<char>(c);if(s.size()>bound)throw e::Error("observation_probe_limit");}return s;}
void emit(const V& value) {std::puts(disked::json::dump(value,limits()).c_str());std::fflush(stdout);}
e::VerificationDefinition definition(const V& v,const std::string& digest) {
    auto value=e::prepare_verification(disked::acquisition::prepare(get(v,"plan")),get(v,"resources"));value.value=v;value.digest=digest;return value;
}
e::VerificationOutcome outcome(const V& v) {
    e::VerificationOutcome o;o.status=text(v,"status");o.diagnostic=text(v,"diagnostic");o.revalidation=text(v,"resource_revalidation");o.before=get(v,"before");o.after=get(v,"after");
    o.records=integer(v,"records");o.consumed_map_bytes=integer(v,"consumed_map_bytes");o.covered_bytes=integer(v,"covered_bytes");o.read_bytes=integer(v,"read_bytes");o.matched_bytes=integer(v,"matched_bytes");
    o.source_bytes=integer(v,"source_bytes");o.substituted_bytes=integer(v,"substituted_bytes");o.sealed=flag(v,"sealed");o.pending=flag(v,"pending");
    if(disked::json::dump(v,limits())!=disked::json::dump(o.view(),limits()))throw e::Error("observation_probe_outcome_shape");return o;
}
V policies() {auto list=V::array();for(unsigned n=0;n<16;++n) {auto p=V::object();unsigned bit=1;for(const auto key:{"identifiers","raw_values","interpretations","customer_data"}) {p.put(key,V::boolean_value((n&bit)!=0));bit<<=1;}list.items.push_back(p);}return list;}
V result(const e::ImageVerificationObservation& observation,const e::AcquisitionCase& report,const V& model) {
    auto views=V::array();for(const auto& p:policies().items) {const e::SupportArtifact artifact(observation,p);views.items.push_back(V::object().put("policy",p).put("support",observation.support(p)).put("artifact",artifact.description()).put("artifact_bytes",V::string(artifact.bytes())));}
    auto exposed=observation.view();const auto original=disked::json::dump(exposed,limits());exposed.fields.clear();
    return V::object().put("observation",observation.view()).put("revision",V::string(observation.revision())).put("projections",views)
        .put("immutable_copy_guard",V::boolean_value(original==disked::json::dump(observation.view(),limits())))
        .put("original_case_claims",get(report.view(),"claims")).put("model_inputs",model);
}
std::uint64_t now() {FILETIME t{};GetSystemTimeAsFileTime(&t);return disked::worker_files::file_time(t);}
int main(int argc,char** argv) {
    try {
        const bool hold=argc==2 && std::strcmp(argv[1],"--hold")==0, exports=argc==2 && std::strcmp(argv[1],"--exports")==0;if(argc!=1 && !hold && !exports)return 2;
        const auto input=disked::json::parse(read(hold||exports,4194304),limits());
        if(text(input,"mode")=="model") {
            e::AcquisitionCase report(get(input,"header"),text(input,"records"));auto raw=text(input,"raw_request");auto d=definition(get(input,"definition"),text(input,"definition_digest"));auto o=outcome(get(input,"outcome"));auto context=get(input,"context");
            const e::ImageVerificationObservation observation(report,raw,d,o,context);const auto snapshot=disked::json::dump(observation.view(),limits());
            raw.clear();d.value.fields.clear();o.status="changed-after-construction";context.fields.clear();
            auto out=result(observation,report,input);out.put("input_snapshot_guard",V::boolean_value(snapshot==disked::json::dump(observation.view(),limits())));
            if(input.find("policy"))out.put("selected_support",observation.support(get(input,"policy")));emit(out);return 0;
        }
        if(text(input,"mode")!="native")throw e::Error("observation_probe_mode");
        disked::FileAcquisitionCase source(text(input,"operation_id"),text(input,"state_directory"));const auto report=source.report();const auto raw=source.request_bytes(),records=source.history_bytes();const auto case_before=source.binding();
        const auto plan=disked::acquisition::prepare(get(get(get(report.view(),"before"),"definition"),"plan"));disked::FileImageVerification verification(plan,text(input,"image"),text(input,"map"));const auto image_before=verification.binding();
        disked::worker_files::Image image;auto code=V::object().put("source_revision",V::string(bootstrap::source_revision)).put("input_digest",V::string(bootstrap::input_digest))
            .put("configuration_digest",V::string(bootstrap::configuration_digest)).put("image_digest",V::string("sha256:"+image.digest))
            .put("target_profile",V::string(bootstrap::target)).put("source_state",V::string(bootstrap::source_state));
        if(hold) {emit(V::object().put("event",V::string("observation-held")).put("pid",V::string(std::to_string(GetCurrentProcessId()))));if(std::getchar()!='x')throw e::Error("observation_probe_release");}
        const auto start=now(),ticks=GetTickCount64();const auto& d=verification.definition();const auto o=verification.execute({d.digest,true,true});auto context=V::object().put("verifier",code).put("case_before",case_before).put("image_before",image_before);
        try {source.check();context.put("case_after",source.binding()).put("case_revalidation",V::string("passed"));}
        catch(const std::exception&) {context.put("case_after",V{}).put("case_revalidation",V::string("unavailable"));}
        try {const auto after=verification.binding();context.put("image_after",after).put("image_binding_revalidation",V::string(disked::json::dump(after,limits())==disked::json::dump(image_before,limits())?"passed":"changed"));}
        catch(const std::exception&) {context.put("image_after",V{}).put("image_binding_revalidation",V::string("unavailable"));}
        context.put("clock",V::object().put("domain",V::string("windows-filetime-wall")).put("started",V::string(std::to_string(start))).put("finished",V::string(std::to_string(now()))).put("elapsed_ms",V::string(std::to_string(GetTickCount64()-ticks))));
        const e::ImageVerificationObservation observation(report,raw,d,o,context);
        auto model=V::object().put("mode",V::string("model")).put("header",get(report.view(),"before")).put("raw_request",V::string(raw)).put("records",V::string(records))
            .put("definition",d.value).put("definition_digest",V::string(d.digest)).put("outcome",o.view()).put("context",context);
        auto out=result(observation,report,model);
        if(exports) {
            const auto& selected=get(input,"exports");if(selected.kind!=V::Kind::array || selected.items.empty() || selected.items.size()>16)throw e::Error("observation_probe_export_limit");auto observations=V::array();
            for(std::size_t i=0;i<selected.items.size();++i) {
                const auto& item=selected.items[i];const e::SupportArtifact artifact(observation,get(item,"policy"));disked::FileReportExport effect(artifact,text(item,"destination"));
                const auto review=V::object().put("schema",V::string("org.disked.image-observation-export-review-prototype/1"))
                    .put("observation_revision",V::string(observation.revision())).put("case_revision",V::string(report.revision()))
                    .put("case_source",case_before).put("image_source",image_before).put("effect",effect.definition().value());
                const auto review_digest=e::export_digest(disked::json::dump(review,limits()));
                bool public_scope_refused=false;
                const auto public_review=V::object().put("schema",V::string("org.disked.acquisition-case-export-definition-prototype/1"))
                    .put("case",V::object().put("operation_id",get(get(report.view(),"before"),"operation_id")).put("revision",V::string(report.revision())))
                    .put("source",case_before).put("effect",effect.definition().value());
                try {e::validate_acquisition_export_review(public_review);}
                catch(const e::Error& error) {public_scope_refused=std::strcmp(error.what(),"case_export_artifact_binding")==0;}
                emit(V::object().put("event",V::string("support-export-reviewed")).put("index",V::string(std::to_string(i))).put("definition",review).put("definition_digest",V::string(review_digest)).put("artifact_bytes",V::string(artifact.bytes())).put("public_scope_refused",V::boolean_value(public_scope_refused)));
                const auto g=disked::json::parse(read(true,16384),limits());if(g.kind!=V::Kind::object || g.fields.size()!=3)throw e::Error("observation_probe_export_grant");
                const auto allowed_digest=text(g,"definition_digest")==review_digest?effect.definition().digest():"";
                const auto written=effect.execute({allowed_digest,flag(g,"report_write"),flag(g,"host_effects")},{},[&] {source.check();verification.binding();});
                observations.items.push_back(V::object().put("definition",review).put("definition_digest",V::string(review_digest)).put("outcome",written.outcome.view()).put("receipt",written.receipt));
            }
            out.put("exports",observations);
        }
        emit(out);return 0;
    }catch(const std::exception& error) {emit(V::object().put("refusal",V::string(error.what())));return 3;}
}
