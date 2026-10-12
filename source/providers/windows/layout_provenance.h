#pragma once
#include "storage_layout.h"
#include "storage_frame_reader.h"
#include "providers/image/file_layout.h"

namespace disked { namespace nt_inventory {
struct OwnedLayoutBinding {
    LayoutBinding comparison;
    std::string file_capture_digest,file_context_digest,storage_context_digest;
};
std::string file_layout_capture_digest(const FileLayoutSnapshot&);
// Pure join of separately owned snapshots. No reader launch, query or grant.
json::Value compare_owned_layout(const StorageFrameSnapshot&,const FileLayoutSnapshot&,const OwnedLayoutBinding&);
}}
