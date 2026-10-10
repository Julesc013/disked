#include "image_collection.h"
#include "file_image_collection.h"
#include "file_export.h"
#include "acquisition_export.h"
#include "local_file.h"
#include <cstdio>
#include <cstring>
namespace e=disked::evidence::proposal;using V=disked::json::Value;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("collection_probe_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw e::Error("collection_probe_shape");return p.text;}
bool flag(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::boolean)throw e::Error("collection_probe_shape");return p.boolean;}
disked::json::Limits limits() {auto l=e::image_collection_limits();l.bytes=33554432;l.string_bytes=2097152;l.values=2097152;l.depth=64;return l;}
std::string read(bool line,std::size_t bound) {std::string s;for(int c=std::getchar();c!=EOF && (!line || c!='\n');c=std::getchar()) {s+=static_cast<char>(c);if(s.size()>bound)throw e::Error("collection_probe_limit");}return s;}
void emit(const V& v) {std::puts(disked::json::dump(v,limits()).c_str());std::fflush(stdout);}
V audit(const e::ImageVerificationCollection& report) {
    const e::CollectionRetentionArtifact retained(report);auto rows=V::array();
    for(unsigned n=0;n<16;++n) {auto policy=V::object();unsigned bit=1;for(const auto key:{"identifiers","raw_values","interpretations","customer_data"}) {policy.put(key,V::boolean_value((n&bit)!=0));bit<<=1;}
        const e::SupportArtifact selected(report,policy);rows.items.push_back(V::object().put("policy",policy).put("support",report.support(policy)).put("artifact",selected.description()).put("artifact_bytes",V::string(selected.bytes())));}
    auto copy=report.view();copy.fields.clear();
    return V::object().put("collection",report.view()).put("revision",V::string(report.revision())).put("retention",retained.description()).put("retention_bytes",V::string(retained.bytes()))
        .put("projections",rows).put("copy_guard",V::boolean_value(!copy.find("schema") && report.view().find("schema")));
}
int main(int argc,char** argv) {
    try {
        const bool save=argc==2 && std::strcmp(argv[1],"--save")==0,hold=argc==2 && std::strcmp(argv[1],"--hold")==0;
        if(argc!=1 && !save && !hold)return 2;const auto input=disked::json::parse(read(save||hold,4194304),limits());const auto mode=text(input,"mode");
        if(mode=="read") {
            disked::FileImageVerificationCollection source(text(input,"path"),text(input,"expected_digest"));const auto snapshot=source.snapshot();const auto binding=source.binding();
            if(hold) {emit(V::object().put("event",V::string("collection-file-held")).put("pid",V::string(std::to_string(GetCurrentProcessId()))));if(std::getchar()!='x')throw e::Error("collection_probe_release");}
            auto result=audit(snapshot);result.put("binding_before",binding);
            try {source.check();result.put("source_state",V::string("passed")).put("binding_after",source.binding());}
            catch(const std::exception& error) {result.put("source_state",V::string("unavailable")).put("binding_after",V{}).put("source_diagnostic",V::string(error.what()));}
            emit(result);return 0;
        }
        auto report=mode=="restore"?e::ImageVerificationCollection::restore(text(input,"retention_bytes")):[&] {
            if(mode!="model")throw e::Error("collection_probe_mode");const auto request=text(input,"raw_request"),history=e::image_collection_bytes(text(input,"raw_history_hex"));
            auto l=e::image_collection_limits();l.bytes=32768;l.values=4096;l.depth=24;const e::AcquisitionCase original(disked::json::parse(request,l),history);
            auto collection=e::ImageVerificationCollection(text(input,"collection_id"),original,request,history);const auto& entries=get(input,"observations");
            if(entries.kind!=V::Kind::array || entries.items.size()>17)throw e::Error("collection_probe_record_limit");
            for(const auto& row:entries.items) {const auto before=disked::json::dump(collection.view(),limits());const auto old_revision=collection.revision();
                const auto observation=e::ImageVerificationObservation::restore(original,request,get(row,"observation"));const auto next=collection.with_observation(observation,get(row,"observer"));
                if(before!=disked::json::dump(collection.view(),limits()) || old_revision!=collection.revision())throw e::Error("collection_probe_snapshot_mutated");collection=next;}
            return collection;
        }();
        auto result=audit(report);if(input.find("policy"))result.put("selected_support",report.support(get(input,"policy")));
        if(input.find("failed_append")) {
            const auto prior=report.revision(),bytes=disked::json::dump(report.view(),limits());const auto& row=get(input,"failed_append");
            const auto& original=get(report.view(),"original_case");const e::AcquisitionCase source(get(original,"before"),e::image_collection_bytes(text(report.view(),"history_hex")));
            const auto observation=e::ImageVerificationObservation::restore(source,text(report.view(),"request_raw"),get(row,"observation"));
            try {report.with_observation(observation,get(row,"observer"));result.put("rejected_append",V::object().put("unexpected_success",V::boolean_value(true)));}
            catch(const std::exception& error) {result.put("rejected_append",V::object().put("diagnostic",V::string(error.what())).put("unchanged",V::boolean_value(prior==report.revision() && bytes==disked::json::dump(report.view(),limits()))));}
        }
        if(save) {
            const auto& items=get(input,"exports");if(items.kind!=V::Kind::array || items.items.empty() || items.items.size()>17)throw e::Error("collection_probe_export_limit");auto saved=V::array();
            for(const auto& item:items.items) {
                const bool private_content=flag(item,"private");const e::ExportArtifact artifact=private_content?e::ExportArtifact(e::CollectionRetentionArtifact(report)):e::ExportArtifact(e::SupportArtifact(report,get(item,"policy")));
                disked::FileReportExport effect(artifact,text(item,"destination"));const auto review=V::object().put("schema",V::string("org.disked.image-collection-export-review-prototype/1"))
                    .put("collection_revision",V::string(report.revision())).put("effect",effect.definition().value());const auto hash=e::export_digest(disked::json::dump(review,limits()));
                bool public_refused=false;const auto& records=get(report.view(),"records");
                if(!records.items.empty()) {const auto& obs=get(records.items.front(),"observation");const auto public_review=V::object().put("schema",V::string("org.disked.acquisition-case-export-definition-prototype/1"))
                    .put("case",V::object().put("operation_id",get(get(obs,"case"),"operation_id")).put("revision",get(report.view(),"case_revision")))
                    .put("source",get(obs,"case_source_before")).put("effect",effect.definition().value());
                    try {e::validate_acquisition_export_review(public_review);}catch(const e::Error& error) {public_refused=std::strcmp(error.what(),"case_export_artifact_binding")==0;}}
                emit(V::object().put("event",V::string("collection-save-reviewed")).put("definition",review).put("definition_digest",V::string(hash)).put("artifact_bytes",V::string(artifact.bytes())).put("public_scope_refused",V::boolean_value(public_refused)));
                const auto grant=disked::json::parse(read(true,16384),limits());if(grant.kind!=V::Kind::object || grant.fields.size()!=4)throw e::Error("collection_probe_grant");
                const auto output=effect.execute({text(grant,"definition_digest")==hash?effect.definition().digest():"",flag(grant,"report_write"),flag(grant,"host_effects"),flag(grant,"private_metadata")});
                saved.items.push_back(V::object().put("definition",review).put("definition_digest",V::string(hash)).put("outcome",output.outcome.view()).put("receipt",output.receipt));
            }result.put("exports",saved);
        }emit(result);return 0;
    }catch(const std::exception& error) {emit(V::object().put("refusal",V::string(error.what())));return 3;}
}
