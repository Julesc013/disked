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
    StorageFrameSnapshot(std::shared_ptr<const StorageFrame> frame,CaptureKey key,json::Value context):frame_(std::move(frame)),key_(std::move(key)),context_(std::move(context)){}
    friend class StorageGraphAdapter;
public:
    const StorageFrame& frame()const{return *frame_;}
    const CaptureKey& key()const{return key_;}
    const json::Value& context()const{return context_;}
};
}}
