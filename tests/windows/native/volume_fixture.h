#pragma once
#include "volume_inventory.h"
namespace disked { namespace nt_fixture {
nt_inventory::VolumeApi api(const json::Value&,const std::function<void()>& notify={});
unsigned call_count();
unsigned close_count();
json::Value calls_trace();
}}
