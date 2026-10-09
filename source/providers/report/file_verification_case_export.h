#pragma once
#include "verification_case_export.h"
#include "file_export.h"
#include <memory>
namespace disked {
struct FileVerificationCaseExportResult {evidence::proposal::VerificationCaseExportOutcome outcome;json::Value receipt;};
// Explicit ordinary metadata sources; private synchronous coordinator only.
// A report snapshot and each source's last observation are separate facts.
class FileVerificationCaseExport final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileVerificationCaseExport(const std::string& operation_id,const std::string& case_directory,
        const std::string& collection_path,const std::string& collection_digest,const json::Value& policy,
        const std::string& destination,const json::Value* reviewed=nullptr);
    ~FileVerificationCaseExport();
    FileVerificationCaseExport(const FileVerificationCaseExport&)=delete;
    FileVerificationCaseExport& operator=(const FileVerificationCaseExport&)=delete;
    const evidence::proposal::AcquisitionVerificationReport& report() const;
    const evidence::proposal::VerificationCaseExportDefinition& definition() const;
    FileVerificationCaseExportResult execute(const evidence::proposal::VerificationCaseExportGrant&,const std::function<bool()>& stop={});
};
}
