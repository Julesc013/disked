#pragma once
#include "volume_namespace.h"
#include "json.h"
#include <functional>
#include <cstdint>
namespace disked { namespace nt_inventory {
struct InventoryPolicy {
    std::uint32_t volumes=64,mounts=64,mount_units=8192;
    bool include_mounts=true;
};
// A private immutable returned value. Observation IDs are capture-local and
// never physical target identities. No public graph/service admission here.
json::Value collect_volume_namespace(VolumeCursor&,std::uint64_t capture_epoch,
    const InventoryPolicy&,const std::function<bool()>& cancelled);
json::Value lossless_name(const std::wstring&);
json::Limits volume_inventory_limits();
}}
