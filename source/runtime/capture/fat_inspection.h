#pragma once
#include "runtime/command/protocol.h"
#include "fat_namespace.h"
#include "fat_capture.h"
#include "fat_retention.h"

namespace disked {
struct FatInspectionRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0;
    std::uint32_t fat_copy = 0, name_code_page = 0;
    bool allocation_scan = false, auxiliary_checks = false, retain_capture = false;
    FatAllocationWindow allocation_window;
    std::vector<FatNameQuery> queries;
};
struct FatInspectionRead {
    enum class Status { Captured, Refused, Unresolved };
    Status status = Status::Unresolved;
    json::Value file, context, worker, frame;
    std::string diagnostic;
    std::uint32_t platform_code = 0;
};
using FatInspectionPort = std::function<FatInspectionRead(const FatInspectionRequest &)>;
bool fat_inspection_parameters(const json::Value &);
bool decode_fat_inspection(const json::Value &, FatInspectionRequest &);
Outcome dispatch_fat_inspection(const std::string &, const json::Value &,
                                const FatInspectionPort &, FatCaptureStore *store = nullptr);
json::Value project_fat_inspection(const FatInspectionRead &);
constexpr std::size_t fat_inspection_response_bytes = 524288;
} // namespace disked
