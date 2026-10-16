#pragma once
#include "runtime/acquisition/fat_tree_commands.h"
#include "runtime/acquisition/fat_tree_watch.h"

namespace disked {
namespace nt_inventory {
FatTreeCommandActions fat_tree_command_actions();
Outcome dispatch_fat_tree_operation(const Registry &, const std::string &request,
                                    const std::string &command, const json::Value &parameters,
                                    const fat_tree_operation::EventSink &sink = {});
} // namespace nt_inventory
} // namespace disked
