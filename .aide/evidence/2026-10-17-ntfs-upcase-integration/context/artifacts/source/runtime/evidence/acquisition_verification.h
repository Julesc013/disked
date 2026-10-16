#pragma once
#include "image_collection.h"
namespace disked { namespace evidence { namespace proposal {
json::Limits acquisition_verification_limits();
// Immutable recorded acquisition and later verification, never latest-image
// authority. Construction checks the exact original raw bytes in both inputs.
class AcquisitionVerificationReport final {
    AcquisitionCase acquisition_;ImageVerificationCollection verification_;
    json::Value view_;std::string revision_;
public:
    AcquisitionVerificationReport(const AcquisitionCase&,const std::string& request,
        const std::string& history,const ImageVerificationCollection&);
    const json::Value& view() const {return view_;}
    const std::string& revision() const {return revision_;}
    json::Value support(const json::Value& policy) const;
};
}}}
