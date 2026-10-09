#pragma once
#include "case_report.h"
#include "operation.h"

namespace disked { namespace evidence { namespace proposal {
// Immutable interpretation of an independently supplied request/history pair.
// Validation proves their contract/chain consistency, not their actor, current
// image bytes, worker exit, or physical origin. No path is dereferenced here.
class AcquisitionCase final {
    json::Value header_,view_;
    acquisition_operation::History history_;
    std::string revision_;
public:
    AcquisitionCase(const json::Value& header,const std::string& records);
    const json::Value& view() const {return view_;}
    const std::string& revision() const {return revision_;}
    json::Value support(const json::Value& policy) const;
};
json::Limits acquisition_case_limits();
void validate_acquisition_case_request(const json::Value&);
}}}
