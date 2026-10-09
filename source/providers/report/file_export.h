#pragma once
#include "report_export.h"
#include <functional>
#include <memory>

namespace disked {
struct FileReportExportError : evidence::proposal::Error {
    std::uint32_t platform_code;
    FileReportExportError(const char* code,std::uint32_t platform=0):Error(code),platform_code(platform) {}
};
struct FileReportExportResult {evidence::proposal::ExportOutcome outcome;json::Value receipt;};
// Private synchronous ordinary-file adapter; public bounded service admission
// remains separate. Preparation creates no output. A session executes once.
class FileReportExport final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileReportExport(const evidence::proposal::SupportArtifact&,const std::string& destination,
        const json::Value* reviewed_definition=nullptr);
    ~FileReportExport();
    FileReportExport(const FileReportExport&)=delete;FileReportExport& operator=(const FileReportExport&)=delete;
    const evidence::proposal::ExportDefinition& definition() const;
    FileReportExportResult execute(const evidence::proposal::ExportGrant&,const std::function<bool()>& stop={},
        const std::function<void()>& revalidate_read_resources={});
};
}
