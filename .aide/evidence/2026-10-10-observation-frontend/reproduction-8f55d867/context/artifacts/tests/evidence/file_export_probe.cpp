#include "file_export.h"
#include "export_fixture.h"
#include <cstdio>
using V=disked::json::Value;namespace e=disked::evidence::proposal;using namespace export_fixture;
int main() {
    try {
        std::string input;char block[4096];for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>65536)return 2;if(n<sizeof(block))break;}
        const auto v=disked::json::parse(input);const auto mode=text(field(v,"mode"));if(mode!="prepare" && mode!="execute")throw e::Error("export_probe_input");
        const auto report=make_case(flag(v,"large"),flag(v,"controls"));const auto policy=v.find("policy")?*v.find("policy"):default_policy();const e::SupportArtifact artifact(report,policy);
        disked::FileReportExport session(artifact,text(field(v,"destination")),v.find("reviewed_definition"));
        auto out=V::object().put("definition",session.definition().value()).put("definition_digest",V::string(session.definition().digest())).put("artifact_preview",preview(artifact));
        if(mode=="execute") {
            const auto cancel=flag(v,"cancel");const auto result=session.execute(grant(v,session.definition().digest()),[cancel] {return cancel;});out.put("outcome",result.outcome.view()).put("receipt",result.receipt);
            if(flag(v,"repeat")) {try {session.execute(grant(v,session.definition().digest()));out.put("repeat",V::string("unexpected_success"));}catch(const std::exception& error) {out.put("repeat",V::string(error.what()));}}
        }
        auto limits=e::case_limits();limits.bytes=2097152;std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const disked::FileReportExportError& error) {
        std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform_code)))).c_str());return 3;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
