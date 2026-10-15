#pragma once
#include "runtime/capture/ntfs_inspection.h"

namespace disked {
NtfsInspectionRead inspect_ntfs_image(const NtfsInspectionRequest &);
} // namespace disked
