#pragma once
#include "ntfs_directory.h"
#include <functional>

namespace disked {
// Private supplied-reader observations. Mapped order and candidate groups do not
// establish host case policy, full collation, alias resolution or lookup rights.
json::Value observe_ntfs_name_order(const NtfsDirectoryRequest &, const RegionReader &);

namespace ntfs_name_order_detail {
// Collaborates with the source-owning Observer. Inputs are its complete owned
// ingredients; output owns completed prefixes if the charge callback stops work.
void collect(const NtfsDirectoryRequest &, const json::Value &directory, const json::Value &upcase,
             const std::function<void(std::size_t)> &charge, json::Value &out);
} // namespace ntfs_name_order_detail
} // namespace disked
