#pragma once
#include "exfat_capture.h"
#include "runtime/command/protocol.h"

namespace disked {
struct ExfatInspectionRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0;
    ExfatUpcaseFormat upcase_format = ExfatUpcaseFormat::Automatic;
};
struct ExfatInspectionRead {
    enum class Status { Captured, Refused, Unresolved };
    Status status = Status::Unresolved;
    json::Value file, context, worker;
    std::string diagnostic;
    std::uint32_t platform_code = 0;
};
using ExfatInspectionPort = std::function<ExfatInspectionRead(const ExfatInspectionRequest &)>;
bool exfat_inspection_parameters(const json::Value &);
bool decode_exfat_inspection(const json::Value &, ExfatInspectionRequest &);
json::Value project_exfat_inspection(const ExfatInspectionRead &, const ExfatInspectionRequest &);
Outcome dispatch_exfat_inspection(const std::string &, const json::Value &,
                                  const ExfatInspectionPort &);
constexpr std::size_t exfat_inspection_response_bytes = 524288;
} // namespace disked
