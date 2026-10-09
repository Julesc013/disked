#pragma once
#include "pipeline.h"
namespace disked { namespace evidence { namespace proposal {
// Private read-only contract. Matching a recorded map authenticates no actor
// and does not establish original-source preservation or acquisition consistency.
struct VerificationDefinition {acquisition::Plan plan;json::Value resources,value;std::string digest;};
struct VerificationGrant {std::string definition_digest;bool image_read=false,map_read=false;};
class VerificationPorts {
public:
    virtual ~VerificationPorts()=default;
    virtual json::Value observe()=0;
    virtual acquisition::Record next_record()=0;
    virtual acquisition::Read read_image(std::uint64_t offset,std::uint32_t size)=0;
    virtual bool stop_requested()=0;
};
struct VerificationOutcome {
    std::string status="refused",diagnostic,revalidation="not_attempted";
    std::uint64_t records=0,consumed_map_bytes=0,covered_bytes=0,read_bytes=0,matched_bytes=0,source_bytes=0,substituted_bytes=0;
    bool sealed=false,pending=false;
    json::Value before,after;
    json::Value view() const;
};
VerificationDefinition prepare_verification(const acquisition::Plan&,const json::Value& resources);
VerificationOutcome verify_image(const VerificationDefinition&,const VerificationGrant&,VerificationPorts&);
}}}
