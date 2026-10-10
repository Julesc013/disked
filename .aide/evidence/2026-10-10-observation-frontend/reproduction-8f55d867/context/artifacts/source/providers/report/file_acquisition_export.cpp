#include "file_acquisition_export.h"
#include "file_case.h"
namespace disked {
namespace e=evidence::proposal;using V=json::Value;
class FileAcquisitionExport::Impl {
public:
    FileAcquisitionCase source;e::SupportArtifact artifact;FileReportExport output;
    e::AcquisitionExportDefinition definition;bool used=false;
    Impl(const std::string& id,const std::string& directory,const V& policy,const std::string& destination,const V* reviewed):
        source(id,directory),artifact(source.report(),policy),output(artifact,destination),definition(source.report(),source.binding(),output.definition()) {
        if(reviewed && json::dump(*reviewed,e::acquisition_export_limits())!=json::dump(definition.value(),e::acquisition_export_limits()))
            throw FileReportExportError("case_export_reviewed_definition_changed");
    }
    FileAcquisitionExportResult execute(const e::AcquisitionExportGrant& grant,const std::function<bool()>& stop) {
        if(used)throw FileReportExportError("case_export_session_used");used=true;V receipt;
        const auto outcome=e::execute_acquisition_export(definition,grant,[&] {return source.binding();},
            [&](const e::ExportGrant& admitted,const std::function<void()>& check) {
                const auto result=output.execute(admitted,stop,check);receipt=result.receipt;return result.outcome;
            });
        return {outcome,V::object().put("definition_digest",V::string(definition.digest())).put("output_receipt",receipt)
            .put("routing_metadata_is_support_export",V::boolean_value(false))};
    }
};
FileAcquisitionExport::FileAcquisitionExport(const std::string& id,const std::string& directory,const V& policy,
    const std::string& destination,const V* reviewed):impl_(new Impl(id,directory,policy,destination,reviewed)) {}
FileAcquisitionExport::~FileAcquisitionExport()=default;
const e::AcquisitionExportDefinition& FileAcquisitionExport::definition() const {return impl_->definition;}
FileAcquisitionExportResult FileAcquisitionExport::execute(const e::AcquisitionExportGrant& grant,const std::function<bool()>& stop) {return impl_->execute(grant,stop);}
}
