#pragma once
#include "report_export.h"
#include <functional>
namespace disked { namespace evidence { namespace proposal {
// Binds immutable case content, current metadata resources and exact output
// effects. JSON bindings describe observations; they authenticate no actor.
class AcquisitionExportDefinition final {
    ExportDefinition effect_;json::Value value_;std::string digest_;
public:
    AcquisitionExportDefinition(const AcquisitionCase&,const json::Value& source,const ExportDefinition&);
    const json::Value& value() const {return value_;}
    const std::string& digest() const {return digest_;}
    const ExportDefinition& effect() const {return effect_;}
};
struct AcquisitionExportGrant {std::string definition_digest;bool case_read=false,report_write=false,host_effects=false;};
struct AcquisitionExportOutcome {
    ExportOutcome output;std::string status="refused",source_state="not_observed",diagnostic;
    json::Value view() const;
};
using CaseSourceObserver=std::function<json::Value()>;
// The effect executor must call the supplied source check before creation and
// each I/O/resource observation; it retains its actual outcome and receipt.
using CheckedExportEffect=std::function<ExportOutcome(const ExportGrant&,const std::function<void()>&)>;
json::Limits acquisition_export_limits();
void validate_case_source(const json::Value&);
void validate_acquisition_export_review(const json::Value&);
AcquisitionExportOutcome execute_acquisition_export(const AcquisitionExportDefinition&,const AcquisitionExportGrant&,
    const CaseSourceObserver&,const CheckedExportEffect&);
}}}
