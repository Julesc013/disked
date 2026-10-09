#include "file_verification_case_export.h"
#include <cstdio>
#include <cstring>
using V=disked::json::Value;namespace e=disked::evidence::proposal;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("verification_case_probe_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& x=get(v,key);if(x.kind!=V::Kind::string)throw e::Error("verification_case_probe_shape");return x.text;}
bool flag(const V& v,const char* key) {const auto p=v.find(key);if(!p)return false;if(p->kind!=V::Kind::boolean)throw e::Error("verification_case_probe_shape");return p->boolean;}
disked::json::Limits limits() {auto l=e::acquisition_verification_limits();l.bytes=16777216;l.string_bytes=4194304;l.values=2097152;return l;}
std::string read(bool line) {std::string s;for(int c=std::getchar();c!=EOF && (!line || c!='\n');c=std::getchar()) {s+=static_cast<char>(c);if(s.size()>4194304)throw e::Error("verification_case_probe_limit");}return s;}
void emit(const V& v) {std::puts(disked::json::dump(v,limits()).c_str());std::fflush(stdout);}
e::VerificationCaseExportGrant grant(const V& input,const std::string& prepared) {
    const auto& g=get(input,"grant");if(g.kind!=V::Kind::object || g.fields.size()!=5)throw e::Error("verification_case_probe_grant");
    const auto d=text(g,"definition_digest");return {d=="$prepared"?prepared:d,flag(g,"case_read"),flag(g,"collection_read"),flag(g,"report_write"),flag(g,"host_effects")};
}
V audit(const e::AcquisitionVerificationReport& report) {
    auto rows=V::array();for(unsigned n=0;n<16;++n) {auto p=V::object();unsigned b=1;for(const auto k:{"identifiers","raw_values","interpretations","customer_data"}) {p.put(k,V::boolean_value((n&b)!=0));b<<=1;}
        const e::SupportArtifact a(report,p);rows.items.push_back(V::object().put("policy",p).put("support",report.support(p)).put("artifact",a.description()).put("artifact_bytes",V::string(a.bytes())));}
    auto changed=report.view();changed.fields.clear();return V::object().put("report",report.view()).put("revision",V::string(report.revision())).put("projections",rows)
        .put("copy_guard",V::boolean_value(!changed.find("schema") && report.view().find("schema")));
}
class ModelPorts final:public e::ExportPorts {
public:
    V resources;std::string bytes;bool created=false;std::function<void()> check;
    ModelPorts(const V& r,const std::function<void()>& c):resources(r),check(c) {}
    V observe() override {check();return resources;}
    void create() override {try {check();}catch(const std::exception& error) {throw e::CreationRefusal(error.what());}created=true;}
    std::uint32_t write(std::uint64_t offset,const char* p,std::uint32_t n) override {check();if(offset!=bytes.size())throw e::Error("verification_case_probe_offset");bytes.append(p,n);return n;}
    void flush() override {check();}
    std::string read(std::uint64_t offset,std::uint32_t n) override {check();return bytes.substr(static_cast<std::size_t>(offset),n);}
    std::uint64_t size() override {check();return bytes.size();}
    bool stop_requested() override {return false;}
};
int main(int argc,char** argv) {
    try {
        const bool hold=argc==2 && std::strcmp(argv[1],"--hold")==0;if(argc!=1 && !hold)return 2;
        const auto input=disked::json::parse(read(hold),limits());const auto mode=text(input,"mode");
        if(mode=="validate") {e::validate_verification_case_export_review(get(input,"definition"));emit(V::object().put("validated",V::boolean_value(true)));return 0;}
        if(mode=="model") {
            const auto request=text(input,"raw_request"),history=e::image_collection_bytes(text(input,"raw_history_hex"));
            const auto collection=e::ImageVerificationCollection::restore(text(input,"collection_bytes"));
            const auto& original=get(collection.view(),"original_case");
            const e::AcquisitionCase acquisition(input.find("case_header")?get(input,"case_header"):get(original,"before"),
                input.find("case_history_hex")?e::image_collection_bytes(text(input,"case_history_hex")):e::image_collection_bytes(text(collection.view(),"history_hex")));
            const e::AcquisitionVerificationReport report(acquisition,request,history,collection);auto out=audit(report);
            if(input.find("sources")) {
                const e::SupportArtifact artifact(report,get(input,"policy"));const e::ExportDefinition effect(artifact,get(input,"resources"));
                const e::VerificationCaseExportDefinition definition(report,get(input,"sources"),effect);std::uint64_t calls=0,effects=0;bool finished=false;
                const auto fault=input.find("fault")?text(input,"fault"):"";ModelPorts ports(get(input,"resources"),{});
                auto observer=[&](bool selected) {++calls;const auto role=selected?"collection":"case";auto v=get(get(input,"sources"),role);
                    const bool first=calls==(selected?2:1),late=finished;
                    if(fault==std::string(role)+"-first-throws" && first || fault==std::string(role)+"-late-throws" && late)throw e::Error("verification_case_probe_source_unavailable");
                    if(fault==std::string(role)+"-first-changed" && first || fault==std::string(role)+"-late-changed" && late)v.put(selected?"digest":"case_revision",V::string("sha256:"+std::string(64,'0')));return v;
                };
                e::VerificationCaseSourceObservers observers{[&] {return observer(false);},[&] {return observer(true);}};
                if(flag(input,"no_case_port"))observers.acquisition={};if(flag(input,"no_collection_port"))observers.collection={};
                e::CheckedExportEffect execute=[&](const e::ExportGrant& admitted,const std::function<void()>& check) {
                    ++effects;if(fault=="executor-throws")throw e::Error("verification_case_probe_effect_unobserved");
                    if(fault=="visit-budget")for(unsigned n=0;n<129;++n)check();ports.check=check;auto result=e::execute_export(effect,admitted,ports);finished=result.status=="completed";
                    if(fault=="contradictory-completion")--result.verified;
                    if(fault=="executor-throws-after")throw e::Error("verification_case_probe_effect_unobserved");return result;
                };
                if(flag(input,"no_effect_port"))execute={};const auto outcome=e::execute_verification_case_export(definition,grant(input,definition.digest()),observers,execute);
                bool old_scope_refused=false;auto old=V::object().put("schema",V::string("org.disked.acquisition-case-export-definition-prototype/1"))
                    .put("case",V::object().put("operation_id",get(get(acquisition.view(),"before"),"operation_id")).put("revision",V::string(acquisition.revision())))
                    .put("source",get(get(input,"sources"),"case")).put("effect",effect.value());
                try {e::validate_acquisition_export_review(old);}catch(const e::Error&) {old_scope_refused=true;}
                out.put("definition",definition.value()).put("definition_digest",V::string(definition.digest())).put("outcome",outcome.view())
                    .put("observer_calls",V::string(std::to_string(calls))).put("effect_calls",V::string(std::to_string(effects))).put("created",V::boolean_value(ports.created))
                    .put("output_bytes",V::string(ports.bytes)).put("old_scope_refused",V::boolean_value(old_scope_refused)).put("file_io",V::boolean_value(false));
            }emit(out);return 0;
        }
        if(mode!="prepare" && mode!="execute")throw e::Error("verification_case_probe_mode");
        std::unique_ptr<disked::FileVerificationCaseExport> session;
        if(input.find("definition")) {
            const auto& d=get(input,"definition");e::validate_verification_case_export_review(d);const auto hash=e::export_digest(disked::json::dump(d,e::verification_case_export_limits()));
            if(mode=="execute") {const auto g=grant(input,hash);if(g.definition_digest!=hash || !g.case_read || !g.collection_read || !g.report_write || !g.host_effects)throw e::Error("verification_case_export_grant");}
            const auto& s=get(d,"sources");const auto& a=get(get(d,"effect"),"artifact");const auto& destination=get(get(get(d,"effect"),"resources"),"destination");
            session.reset(new disked::FileVerificationCaseExport(text(get(d,"report"),"case_operation_id"),text(get(get(s,"case"),"store"),"path"),
                text(get(s,"collection"),"path"),text(get(s,"collection"),"digest"),get(a,"policy"),text(destination,"location"),&d));
        }else session.reset(new disked::FileVerificationCaseExport(text(input,"case_operation_id"),text(input,"case_directory"),text(input,"collection_path"),text(input,"collection_digest"),get(input,"policy"),text(input,"destination")));
        auto out=audit(session->report());out.put("definition",session->definition().value()).put("definition_digest",V::string(session->definition().digest())).put("file_io",V::boolean_value(true));
        V approved=input;if(hold) {auto ready=out;ready.put("event",V::string("verification-case-reviewed"));emit(ready);approved=disked::json::parse(read(true),limits());}
        if(mode=="execute" || hold) {
            unsigned stops=0;const auto stop_after=approved.find("stop_after")?std::stoul(text(approved,"stop_after")):0;
            const auto result=session->execute(grant(approved,session->definition().digest()),[&] {return flag(approved,"cancel_before") || (stop_after && ++stops>=stop_after);});
            out.put("outcome",result.outcome.view()).put("receipt",result.receipt);
            if(flag(approved,"second_call")) {try {session->execute(grant(approved,session->definition().digest()));throw e::Error("verification_case_probe_second_execution");}
                catch(const disked::FileReportExportError& error) {out.put("second_call_refusal",V::string(error.what()));}}
        }emit(out);return 0;
    }catch(const std::exception& error) {emit(V::object().put("refusal",V::string(error.what())));return 3;}
}
