#include "file_acquisition_export.h"
#include "file_case.h"
#include "worker_files.h"
#include <cstdio>
using V=disked::json::Value;namespace e=disked::evidence::proposal;
const V& field(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw e::Error("joint_probe_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=field(v,key);if(p.kind!=V::Kind::string)throw e::Error("joint_probe_shape");return p.text;}
bool flag(const V& v,const char* key) {const auto p=v.find(key);if(!p)return false;if(p->kind!=V::Kind::boolean)throw e::Error("joint_probe_shape");return p->boolean;}
e::AcquisitionExportGrant grant(const V& input,const std::string& prepared) {
    const auto& g=field(input,"grant");if(g.kind!=V::Kind::object || g.fields.size()!=4)throw e::Error("joint_probe_shape");
    const auto hash=text(g,"definition_digest");return {hash=="$prepared"?prepared:hash,flag(g,"case_read"),flag(g,"report_write"),flag(g,"host_effects")};
}
class ModelPorts final:public e::ExportPorts {
public:
    V resources;std::string bytes;bool created=false;std::function<void()> check;
    ModelPorts(const V& r,const std::function<void()>& c):resources(r),check(c) {}
    V observe() override {check();return resources;}
    void create() override {try {check();}catch(const std::exception& error) {throw e::CreationRefusal(error.what());}created=true;}
    std::uint32_t write(std::uint64_t offset,const char* p,std::uint32_t n) override {check();if(offset!=bytes.size())throw e::Error("joint_probe_offset");bytes.append(p,n);return n;}
    void flush() override {check();}
    std::string read(std::uint64_t offset,std::uint32_t n) override {check();return bytes.substr(static_cast<std::size_t>(offset),n);}
    std::uint64_t size() override {check();return bytes.size();}
    bool stop_requested() override {return false;}
};
int main() {
    try {
        std::string bytes;char chunk[4096];for(;;) {const auto n=std::fread(chunk,1,sizeof(chunk),stdin);bytes.append(chunk,n);if(bytes.size()>4194304)return 2;if(n<sizeof(chunk))break;}
        auto limits=e::acquisition_case_limits();limits.bytes=4194304;limits.string_bytes=1048576;const auto input=disked::json::parse(bytes,limits);
        V out;
        if(text(input,"mode")=="model") {
            const e::AcquisitionCase report(field(input,"header"),text(input,"records"));
            const e::SupportArtifact artifact(report,field(input,"policy"));
            const e::ExportDefinition effect(artifact,field(input,"resources"));
            const e::AcquisitionExportDefinition definition(report,field(input,"source"),effect);
            const auto fault=input.find("fault")?text(input,"fault"):"";unsigned observations=0,effects=0;bool created=false,finished=false;std::string written;
            const auto outcome=e::execute_acquisition_export(definition,grant(input,definition.digest()),[&] {
                ++observations;if(fault=="source-unobserved")throw e::Error("joint_probe_source_unobserved");
                auto source=field(input,"source");
                if(fault=="source-before" || (fault=="source-before-create" && observations>=3) ||
                    (fault=="source-after-create" && created) || (fault=="source-after-write" && !written.empty()) || (fault=="source-after-output" && finished))
                    source.fields["files"].items[0].fields["metadata"].fields["changed"]=V::string("1");
                return source;
            },[&](const e::ExportGrant& allowed,const std::function<void()>& check) {
                ++effects;if(fault=="executor-throws-before")throw e::Error("joint_probe_effect_unobserved");
                // Mirror the actual native before-I/O source checks. Observed
                // side effects here are pure model bytes, never host files.
                class Ports final:public e::ExportPorts {
                    ModelPorts p;bool& created;std::string& written;
                public:
                    Ports(const V& resources,const std::function<void()>& c,bool& b,std::string& s):p(resources,c),created(b),written(s) {}
                    V observe() override {return p.observe();}
                    void create() override {p.create();created=p.created;}
                    std::uint32_t write(std::uint64_t offset,const char* b,std::uint32_t n) override {const auto count=p.write(offset,b,n);written=p.bytes;return count;}
                    void flush() override {p.flush();}
                    std::string read(std::uint64_t offset,std::uint32_t n) override {return p.read(offset,n);}
                    std::uint64_t size() override {return p.size();}
                    bool stop_requested() override {return false;}
                } ports(field(input,"resources"),check,created,written);
                const auto result=e::execute_export(effect,allowed,ports);finished=result.status=="completed";
                if(fault=="executor-throws-after")throw e::Error("joint_probe_effect_unobserved");return result;
            });
            out=V::object().put("definition",definition.value()).put("definition_digest",V::string(definition.digest())).put("outcome",outcome.view())
                .put("source_observations",V::string(std::to_string(observations))).put("effect_calls",V::string(std::to_string(effects)))
                .put("created",V::boolean_value(created)).put("artifact_bytes",V::string(artifact.bytes())).put("output_bytes",V::string(written))
                .put("file_io",V::boolean_value(false));
        }else {
            const auto mode=text(input,"mode");if(mode!="prepare" && mode!="execute")throw e::Error("joint_probe_mode");
            std::unique_ptr<disked::FileAcquisitionExport> session;
            if(mode=="execute" && input.find("definition")) {
                const auto& reviewed=field(input,"definition");e::validate_acquisition_export_review(reviewed);
                const auto hash=e::export_digest(disked::json::dump(reviewed,e::acquisition_export_limits()));const auto g=grant(input,hash);
                // Check supplied execution authority before reconstructing or
                // opening any selected metadata/output/producer resources.
                if(g.definition_digest!=hash || !g.case_read || !g.report_write || !g.host_effects)throw e::Error("case_export_grant");
                session.reset(new disked::FileAcquisitionExport(text(field(reviewed,"case"),"operation_id"),text(field(field(reviewed,"source"),"store"),"path"),
                    field(field(field(reviewed,"effect"),"artifact"),"policy"),text(field(field(field(reviewed,"effect"),"resources"),"destination"),"location"),&reviewed));
            }else session.reset(new disked::FileAcquisitionExport(text(input,"operation_id"),text(input,"state_directory"),field(input,"policy"),text(input,"destination")));
            out=V::object().put("definition",session->definition().value()).put("definition_digest",V::string(session->definition().digest())).put("file_io",V::boolean_value(true));
            if(mode=="execute") {
                const auto result=session->execute(grant(input,session->definition().digest()),[&] {return flag(input,"cancel_before");});
                out.put("outcome",result.outcome.view()).put("receipt",result.receipt);
                if(flag(input,"second_call")) {try {session->execute(grant(input,session->definition().digest()));throw e::Error("joint_probe_second_execution");}
                    catch(const disked::FileReportExportError& error) {out.put("second_call_refusal",V::string(error.what()));}}
            }
        }
        std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const disked::worker_files::Failure& error) {
        std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform)))).c_str());return 3;
    }catch(const disked::FileReportExportError& error) {
        std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform_code)))).c_str());return 3;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
