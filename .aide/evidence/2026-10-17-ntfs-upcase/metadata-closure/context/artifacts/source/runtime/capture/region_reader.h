#pragma once
#include "portable/primitives/extent.h"
#include "portable/primitives/view.h"
#include <functional>

namespace disked {
// Private checked-region capture contract. The caller retains immutable views
// until the observation returns; no view or callback escapes in owned results.
using RegionReader = std::function<de_view(const de_byte_extent &)>;
} // namespace disked
