#pragma once
#include "runtime/command/json.h"

namespace disked {
namespace nt_inventory {
// Read retained control artifacts and independently observe process identities.
// Cancellation is only a request against the exact live bound owner; never
// execution, replay, restart, cleanup or a generic process-termination path.
json::Value observe_fat_tree_operation(const std::string &operation, const std::string &store,
                                       bool cancel = false);
} // namespace nt_inventory
} // namespace disked
