#pragma once
#include "runtime/command/json.h"
#include "runtime/acquisition/fat_tree_watch.h"

namespace disked {
namespace nt_inventory {
// Read retained control artifacts and independently observe process identities.
// Cancellation is only a request against the exact live bound owner; never
// execution, replay, restart, cleanup or a generic process-termination path.
json::Value observe_fat_tree_operation(const std::string &operation, const std::string &store,
                                       bool cancel = false,
                                       fat_tree_operation::History *retained = nullptr);
// Following is bounded between native calls. It cannot impose a deadline on
// a blocked OS API; public callers also require the existing request containment.
json::Value watch_fat_tree_operation(const std::string &operation, const std::string &store,
                                     const json::Value &options,
                                     const fat_tree_operation::EventSink &sink = {},
                                     const std::string &request = "private-watch");
json::Value wait_fat_tree_operation(const std::string &operation, const std::string &store,
                                    std::uint32_t follow_ms,
                                    const fat_tree_operation::EventSink &sink = {});
} // namespace nt_inventory
} // namespace disked
