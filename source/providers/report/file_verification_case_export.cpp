#include "file_verification_case_export.h"
#include "file_case.h"
#include "file_image_collection.h"
#include "local_file.h"
namespace disked {
namespace e=evidence::proposal;using V=json::Value;
namespace {
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw FileReportExportError("verification_case_native_shape");return *p;}
bool same_path(const std::string& a,const std::string& b) {
    const auto x=local_file::path_for(a),y=local_file::path_for(b);
    const auto equal=CompareStringOrdinal(x.c_str(),-1,y.c_str(),-1,TRUE);
    if(!equal)throw FileReportExportError("verification_case_path_comparison",GetLastError());return equal==CSTR_EQUAL;
}
void aliases(const V& value) {
    const auto& sources=get(value,"sources");const auto destination=get(get(get(get(value,"effect"),"resources"),"destination"),"location").text;
    if(same_path(destination,get(get(sources,"collection"),"path").text))throw FileReportExportError("verification_case_output_alias");
    const auto& store=get(get(sources,"case"),"store");for(const auto& child:get(store,"children").items)
        if(same_path(destination,get(store,"path").text+"\\"+child.text))throw FileReportExportError("verification_case_output_alias");
}
}
class FileVerificationCaseExport::Impl {
public:
    FileAcquisitionCase acquisition;FileImageVerificationCollection collection;e::AcquisitionVerificationReport report;
    e::SupportArtifact artifact;FileReportExport output;e::VerificationCaseExportDefinition definition;bool used=false;
    Impl(const std::string& id,const std::string& directory,const std::string& selected,const std::string& digest,
        const V& policy,const std::string& destination,const V* reviewed):acquisition(id,directory),collection(selected,digest),
        report(acquisition.report(),acquisition.request_bytes(),acquisition.history_bytes(),collection.snapshot()),artifact(report,policy),output(artifact,destination),
        definition(report,V::object().put("case",acquisition.binding()).put("collection",collection.binding()),output.definition()) {
        aliases(definition.value());if(reviewed) {
            e::validate_verification_case_export_review(*reviewed);
            if(json::dump(*reviewed,e::verification_case_export_limits())!=json::dump(definition.value(),e::verification_case_export_limits()))
                throw FileReportExportError("verification_case_reviewed_definition_changed");
        }
    }
    FileVerificationCaseExportResult execute(const e::VerificationCaseExportGrant& grant,const std::function<bool()>& stop) {
        if(used)throw FileReportExportError("verification_case_session_used");used=true;V receipt;
        const e::VerificationCaseSourceObservers observers{[&] {return acquisition.binding();},[&] {return collection.binding();}};
        const auto outcome=e::execute_verification_case_export(definition,grant,observers,[&](const e::ExportGrant& admitted,const std::function<void()>& check) {
            const auto result=output.execute(admitted,stop,check);receipt=result.receipt;return result.outcome;
        });
        return {outcome,V::object().put("definition_digest",V::string(definition.digest())).put("output_receipt",receipt)
            .put("routing_metadata_is_support_export",V::boolean_value(false))};
    }
};
FileVerificationCaseExport::FileVerificationCaseExport(const std::string& id,const std::string& directory,const std::string& selected,
    const std::string& digest,const V& policy,const std::string& destination,const V* reviewed):impl_(new Impl(id,directory,selected,digest,policy,destination,reviewed)) {}
FileVerificationCaseExport::~FileVerificationCaseExport()=default;
const e::AcquisitionVerificationReport& FileVerificationCaseExport::report() const {return impl_->report;}
const e::VerificationCaseExportDefinition& FileVerificationCaseExport::definition() const {return impl_->definition;}
FileVerificationCaseExportResult FileVerificationCaseExport::execute(const e::VerificationCaseExportGrant& grant,const std::function<bool()>& stop) {return impl_->execute(grant,stop);}
}
