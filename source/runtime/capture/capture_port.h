#pragma once
#include "json.h"
#include "gpt_repair.h"
#include <cstdint>
#include <functional>
#include <string>

namespace disked {
// Private inward-facing owned capture values. No OS or provider dependency.
struct ImageCaptureError : std::runtime_error {
    std::uint32_t platform_code;
    ImageCaptureError(const char* code,std::uint32_t platform=0):
        std::runtime_error(code),platform_code(platform) {}
};
struct CapturedImage {
    json::Value report;
    json::Value region_manifest;
    bool repair_captured=false;
    planner::proposal::GptRepairCapture repair;
    std::string repair_digest;
};
using ImageCapture=std::function<CapturedImage(const std::string&,std::uint32_t,bool)>;
}
