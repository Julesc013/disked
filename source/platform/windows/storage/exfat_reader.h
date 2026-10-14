#pragma once
#include "runtime/capture/exfat_inspection.h"

namespace disked {
ExfatInspectionRead inspect_exfat_image(const ExfatInspectionRequest &);
} // namespace disked
