#pragma once
#include "capture_port.h"

namespace disked {
// Private Windows ordinary-local-file capture API; command projection is separate.
// Performs synchronous bounded metadata I/O; a caller must contain its wait.
CapturedImage capture_raw_image(const std::string& path,std::uint32_t logical_block_bytes);
}
