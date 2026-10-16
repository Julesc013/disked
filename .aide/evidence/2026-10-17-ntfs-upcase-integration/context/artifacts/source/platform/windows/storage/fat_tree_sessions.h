#pragma once
#include "runtime/capture/fat_tree_session.h"

namespace disked {
namespace nt_inventory {
// Opens only an ordinary local file. The cursor keeps source, ancestry and
// actual process handles alive until its child's exit is observed.
std::unique_ptr<FatTreeCursor> open_fat_tree_cursor(const FatTreeOpenRequest &);
} // namespace nt_inventory
} // namespace disked
