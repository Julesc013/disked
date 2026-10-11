#pragma once
#include "storage_frame_reader.h"

namespace disked { namespace nt_inventory {
struct IdentityBinding {CaptureKey capture;std::string frame_digest,context_digest;};
class StorageIdentityObservation final {
    const json::Value value_;
    explicit StorageIdentityObservation(json::Value value):value_(std::move(value)){}
    friend std::shared_ptr<const StorageIdentityObservation> observe_storage_identity(const StorageFrameSnapshot&,const IdentityBinding&);
public:
    const json::Value& value()const{return value_;}
};
json::Limits storage_identity_limits();
std::string storage_identity_digest(const StorageIdentityObservation&);
// Pure derivation from an actual owned frame; no media identity or storage grant.
std::shared_ptr<const StorageIdentityObservation> observe_storage_identity(const StorageFrameSnapshot&,const IdentityBinding&);
struct IdentityComparisonBinding {std::string previous_digest,current_digest,previous_subject,current_subject;};
// Explicit lookup continuity, not automatic identity matching. No I/O or effect.
json::Value compare_storage_identity(const StorageIdentityObservation&,const StorageIdentityObservation&,const IdentityComparisonBinding&);
}}
