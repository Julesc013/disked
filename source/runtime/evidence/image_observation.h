#pragma once
#include "acquisition_case.h"
#include "image_verification.h"
namespace disked { namespace evidence { namespace proposal {
// Immutable historical observation. Its hash authenticates no actor and grants
// no present-day access. Case applicability and observed image bytes stay apart.
class ImageVerificationObservation final {
    json::Value view_;std::string revision_;
public:
    ImageVerificationObservation(const AcquisitionCase&,const std::string& raw_request,
        const VerificationDefinition&,const VerificationOutcome&,const json::Value& context);
    const json::Value& view() const {return view_;}
    const std::string& revision() const {return revision_;}
    json::Value support(const json::Value& policy) const;
};
json::Limits image_observation_limits();
}}}
