#pragma once
#include "storage_inventory.h"
#include "raw_layout.h"

namespace disked { namespace nt_inventory {
// A caller-declared fixture correlation, not media identity, an owned-reader
// authentication proof, or a storage grant. Both content digests are mandatory.
struct LayoutBinding {CaptureKey capture;std::string subject,frame_digest,raw_digest;};
json::Limits layout_comparison_limits();
std::string raw_layout_digest(const RawPartitionLayout&);
std::string storage_layout_frame_digest(const StorageFrame&);
// Pure comparison of immutable observations; performs no query, open or effect.
json::Value compare_storage_layout(const StorageFrame&,const RawPartitionLayout&,const LayoutBinding&);
}}
