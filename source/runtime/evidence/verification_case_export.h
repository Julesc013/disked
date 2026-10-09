#pragma once
#include "acquisition_verification.h"
#include "acquisition_export.h"
namespace disked { namespace evidence { namespace proposal {
json::Limits verification_case_export_limits();
void validate_verification_collection_source(const json::Value&);
void validate_verification_case_export_review(const json::Value&);
class VerificationCaseExportDefinition final {
    ExportDefinition effect_;json::Value value_;std::string digest_;
public:
    VerificationCaseExportDefinition(const AcquisitionVerificationReport&,const json::Value& sources,const ExportDefinition&);
    const json::Value& value() const {return value_;}
    const std::string& digest() const {return digest_;}
    const ExportDefinition& effect() const {return effect_;}
};
struct VerificationCaseExportGrant {std::string definition_digest;bool case_read=false,collection_read=false,report_write=false,host_effects=false;};
struct VerificationCaseExportOutcome {
    ExportOutcome output;std::string status="refused",diagnostic,case_state="not_observed",collection_state="not_observed";
    std::uint64_t checks=0,case_checked=0,collection_checked=0;
    json::Value view() const;
};
struct VerificationCaseSourceObservers {CaseSourceObserver acquisition,collection;};
VerificationCaseExportOutcome execute_verification_case_export(const VerificationCaseExportDefinition&,const VerificationCaseExportGrant&,
    const VerificationCaseSourceObservers&,const CheckedExportEffect&);
}}}
