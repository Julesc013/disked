#pragma once
#include "acquisition_export.h"
#include "file_export.h"
#include <memory>
namespace disked {
struct FileAcquisitionExportResult {evidence::proposal::AcquisitionExportOutcome outcome;json::Value receipt;};
// Ordinary metadata reads and report-file writes only. Private synchronous
// admission contract; public worker containment/frontend integration pending.
class FileAcquisitionExport final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileAcquisitionExport(const std::string& operation_id,const std::string& state_directory,
        const json::Value& policy,const std::string& destination,const json::Value* reviewed=nullptr);
    ~FileAcquisitionExport();
    FileAcquisitionExport(const FileAcquisitionExport&)=delete;FileAcquisitionExport& operator=(const FileAcquisitionExport&)=delete;
    const evidence::proposal::AcquisitionExportDefinition& definition() const;
    FileAcquisitionExportResult execute(const evidence::proposal::AcquisitionExportGrant&,const std::function<bool()>& stop={});
};
}
