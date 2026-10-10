#pragma once
#include "storage_inventory.h"
namespace disked { namespace nt_inventory {
// Private fixture selection: generated pseudo-handles, never deserialized OS
// handles or paths selected by a disk number. Validate before child creation.
std::vector<StorageSubject> storage_fixture_subjects(const json::Value&);
// Pure bounded receipt conformance, not provenance or native dispatch.
std::shared_ptr<const StorageFrame> read_storage_frame(const json::Value&,const json::Value& fixture,std::uint64_t,const StorageQueryPolicy&,StorageFrameProfile profile=StorageFrameProfile::Metadata);
}}
