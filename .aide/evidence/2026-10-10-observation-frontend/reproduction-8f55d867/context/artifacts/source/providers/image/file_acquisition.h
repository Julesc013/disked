#pragma once
#include "pipeline.h"
#include <memory>
#include <functional>

namespace disked {
struct FileAcquisitionRequest {
    std::string source,destination,map;
    bool resume=false,explicit_options=false;
    std::uint32_t chunk_bytes=65536,retries=0;
    std::string read_policy="ordinary",substitution="stop";
};
struct FileAcquisitionError : acquisition::Error {
    std::uint32_t platform_code;
    FileAcquisitionError(const char* code,std::uint32_t platform=0):acquisition::Error(code),platform_code(platform) {}
};
struct FileAcquisitionResult {acquisition::Outcome outcome;json::Value receipt;};
struct FileAcquisitionHooks {
    std::string attempt_id;
    std::function<bool()> stop;
    std::function<void(const acquisition::Outcome&)> checkpoint;
};
// Private Windows file adapter. Preparation reads metadata/header/code only.
// It holds source/parent/code generations; execution separately grants effects.
class FileAcquisition {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    explicit FileAcquisition(const FileAcquisitionRequest&,const json::Value* reviewed_definition=nullptr);
    ~FileAcquisition();
    FileAcquisition(const FileAcquisition&)=delete;FileAcquisition& operator=(const FileAcquisition&)=delete;
    const acquisition::Plan& plan() const;
    FileAcquisitionResult execute(const acquisition::Grant&,const FileAcquisitionHooks& hooks={});
};
}
