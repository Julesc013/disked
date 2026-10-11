#pragma once
#include "storage_inventory.h"
namespace disked { namespace nt_inventory {
// Private fixture selection: generated pseudo-handles, never deserialized OS
// handles or paths selected by a disk number. Validate before child creation.
std::vector<StorageSubject> storage_fixture_subjects(const json::Value&);
// Pure bounded receipt conformance, not provenance or native dispatch.
std::shared_ptr<const StorageFrame> read_storage_frame(const json::Value&,const json::Value& fixture,std::uint64_t,const StorageQueryPolicy&,StorageFrameProfile profile=StorageFrameProfile::Metadata);
class StorageGraphAdapter;
class StorageFrameSnapshot final {
    const std::shared_ptr<const StorageFrame> frame_;
    const CaptureKey key_;
    const json::Value context_;
    const std::string frame_digest_,context_digest_;
    StorageFrameSnapshot(std::shared_ptr<const StorageFrame> frame,CaptureKey key,json::Value context):frame_(std::move(frame)),key_(std::move(key)),context_(std::move(context)),
        frame_digest_(digest_sha256(json::dump(frame_->value(),storage_observation_limits()))),context_digest_(digest_sha256(json::dump(context_))){}
    friend class StorageGraphAdapter;
public:
    const StorageFrame& frame()const{return *frame_;}
    const CaptureKey& key()const{return key_;}
    const json::Value& context()const{return context_;}
    const std::string& frame_digest()const{return frame_digest_;}
    const std::string& context_digest()const{return context_digest_;}
};
}}
