#pragma once
#include "image_verification.h"
#include <memory>
#include <functional>
namespace disked {
struct FileVerificationError : std::runtime_error {
    std::uint32_t platform_code;
    FileVerificationError(const char* code,std::uint32_t platform=0):std::runtime_error(code),platform_code(platform) {}
};
// Explicit selected paths only. Holds ordinary read handles and strong parents.
// Synchronous private qualification port, not bounded OS-latency containment.
class FileImageVerification final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileImageVerification(const acquisition::Plan&,const std::string& image,const std::string& map);
    ~FileImageVerification();
    FileImageVerification(const FileImageVerification&)=delete;FileImageVerification& operator=(const FileImageVerification&)=delete;
    const evidence::proposal::VerificationDefinition& definition() const;
    json::Value binding() const;
    evidence::proposal::VerificationOutcome execute(const evidence::proposal::VerificationGrant&,
        const std::function<bool()>& stop={},const std::function<void(const evidence::proposal::VerificationOutcome&)>& progress={});
};
}
