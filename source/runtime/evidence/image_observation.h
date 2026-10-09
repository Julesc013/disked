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
    static ImageVerificationObservation restore(const AcquisitionCase&,const std::string& raw_request,
        const json::Value& retained);
    const json::Value& view() const {return view_;}
    const std::string& revision() const {return revision_;}
    json::Value support(const json::Value& policy) const;
};
json::Limits image_observation_limits();
// Shared strict relationships for durable verification records and restore.
json::Value verification_image_resources(const json::Value& binding);
void validate_verifier_code(const json::Value&);
VerificationOutcome restore_verification_outcome(const VerificationDefinition&,const json::Value&);
}}}
