#pragma once
#include "runtime/command/protocol.h"
#include "capture_port.h"
#include "fat_inspection.h"

namespace disked {
// Initial ordinary-local-raw-file prototype. Not a public storage ABI.
bool image_command(const std::string& command);
Outcome dispatch_image(const std::string& request,const std::string& command,
    const json::Value& parameters,const ImageCapture& capture,const std::string& provider,
    const FatInspectionPort& fat={}, FatCaptureStore *store=nullptr);
}
