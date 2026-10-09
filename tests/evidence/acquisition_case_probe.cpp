#include "file_case.h"
#include "file_export.h"
#include "worker_files.h"
#include <cstdio>
#include <cstring>
using V=disked::json::Value;namespace e=disked::evidence::proposal;
const V& field(const V& v,const char* name) {const auto p=v.find(name);if(!p)throw e::Error("case_probe_shape");return *p;}
std::string text(const V& v,const char* name) {const auto& p=field(v,name);if(p.kind!=V::Kind::string)throw e::Error("case_probe_shape");return p.text;}
int main(int argc,char** argv) {
    try {
        const bool hold=argc==2 && std::strcmp(argv[1],"--hold")==0;
        if(argc!=1 && !hold)return 2;
        std::string bytes;
        if(hold) {for(int c=std::getchar();c!=EOF && c!='\n';c=std::getchar()) {bytes+=static_cast<char>(c);if(bytes.size()>4194304)return 2;}}
        else {char chunk[4096];for(;;) {const auto n=std::fread(chunk,1,sizeof(chunk),stdin);bytes.append(chunk,n);if(bytes.size()>4194304)return 2;if(n<sizeof(chunk))break;}}
        auto limits=e::acquisition_case_limits();limits.bytes=4194304;limits.string_bytes=1048576;const auto input=disked::json::parse(bytes,limits);
        std::unique_ptr<disked::FileAcquisitionCase> source;std::unique_ptr<e::AcquisitionCase> model;
        if(input.find("header"))model.reset(new e::AcquisitionCase(field(input,"header"),text(input,"records")));
        else source.reset(new disked::FileAcquisitionCase(text(input,"operation_id"),text(input,"state_directory")));
        if(hold) {
            if(!source)throw e::Error("case_probe_source_required");
            std::puts(disked::json::dump(V::object().put("event",V::string("case-held")).put("pid",V::string(std::to_string(GetCurrentProcessId())))).c_str());std::fflush(stdout);
            if(std::getchar()!='x')throw e::Error("case_probe_release");source->check();
        }
        const auto& report=source?source->report():*model;const e::SupportArtifact artifact(report,field(input,"policy"));
        auto out=V::object().put("case",report.view()).put("case_revision",V::string(report.revision()))
            .put("artifact",artifact.description()).put("artifact_bytes",V::string(artifact.bytes()));
        if(source)out.put("source_binding",source->binding());
        if(input.find("destination")) {
            disked::FileReportExport target(artifact,text(input,"destination"));
            e::ExportGrant grant{target.definition().digest(),true,true};const auto result=target.execute(grant);
            out.put("export_outcome",result.outcome.view()).put("export_receipt",result.receipt);
            // An observation after an effect cannot erase the actual output
            // receipt. The frozen artifact and current source applicability
            // are separate; public joint-resource admission remains pending.
            if(source) {
                try {source->check();out.put("source_revalidation",V::string("passed"));}
                catch(const std::exception& error) {out.put("source_revalidation",V::string("changed")).put("source_diagnostic",V::string(error.what()));}
            }
        }
        // A returned view cannot edit the immutable report or later projection.
        auto changed=report.view();changed.fields.clear();out.put("revision_after_view_edit",V::string(report.revision()));
        std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const disked::worker_files::Failure& error) {
        std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform)))).c_str());return 3;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
