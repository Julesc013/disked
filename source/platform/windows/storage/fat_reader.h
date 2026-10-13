#pragma once
#include "runtime/capture/fat_inspection.h"

namespace disked {
// Native binding for the runtime port; all source/worker handles remain inside this call.
FatInspectionRead inspect_fat_image(const FatInspectionRequest &);
std::string new_fat_capture_domain();
} // namespace disked
