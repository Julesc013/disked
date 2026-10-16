#pragma once
#include "runtime/capture/fat_namespace.h"

namespace disked {
// Explicit installed code page, current-host text APIs and rule model only.
// Does not mount, create a name/path or qualify a storage driver's lookup rules.
FatNameConsumer windows_fat_name_consumer(std::uint32_t code_page);
} // namespace disked
