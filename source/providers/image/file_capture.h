#pragma once
#include "json.h"
#include <cstdint>
#include <string>

namespace disked {
struct ImageCaptureError : std::runtime_error {
    std::uint32_t platform_code;
    ImageCaptureError(const char* code,std::uint32_t platform=0):
        std::runtime_error(code),platform_code(platform) {}
};
struct CapturedImage {
    json::Value report;
    // Complete owned metadata-range receipt; the bounded report binds its hash.
    // Neither object contains raw reader borrows or an open source handle.
    json::Value region_manifest;
};
// Private Windows ordinary-local-file profile. No product command admission.
// Performs synchronous bounded metadata I/O; a caller must contain its wait.
CapturedImage capture_raw_image(const std::string& path,std::uint32_t logical_block_bytes);
}
