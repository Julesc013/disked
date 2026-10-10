#pragma once
#include "storage_queries.h"
namespace disked { namespace nt_storage_fixture {
nt_inventory::StorageQueryApi api(const json::Value&,const std::function<void()>& notify={});
unsigned call_count();unsigned error_count();json::Value calls_trace();
}}
