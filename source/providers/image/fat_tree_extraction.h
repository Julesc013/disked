#pragma once
#include "fat_tree_file.h"

namespace disked {
struct FatTreeExtractionRequest {
    FatTreeInput tree;
    std::string destination, ledger;
    FatMetadataPolicy metadata;
    std::size_t entries = 65536, directories = 4096, metadata_bytes = 16777216, pages = 65536;
    std::uint64_t content_bytes = 1099511627776ULL, ledger_bytes = 1073741824;
};
struct FatTreeExtractionGrant {
    std::string definition_digest;
    bool source_read = false, destination_write = false, ledger_write = false, host_effects = false;
};
struct FatTreeExtractionHooks {
    std::string attempt_id;
    std::function<bool()> stop;
    // Trusted controller callback, never selected by source metadata or JSON.
    std::function<void(const char *boundary)> boundary;
};
struct FatTreeExtractionError : std::runtime_error {
    std::uint32_t platform_code;
    std::string platform_domain;
    explicit FatTreeExtractionError(const char *code, std::uint32_t platform = 0,
                                    const char *domain = "win32")
        : std::runtime_error(code), platform_code(platform), platform_domain(domain) {
    }
};
// Private ordinary-file backend. Constructor prepares the complete selected
// namespace without output. Execution separately requires the exact grant.
// Synchronous: contained process/actual-exit qualification is required before
// frontend admission. No overwrite, deletion, source writes or automatic resume.
class FatTreeExtraction final {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    explicit FatTreeExtraction(const FatTreeExtractionRequest &);
    ~FatTreeExtraction();
    FatTreeExtraction(const FatTreeExtraction &) = delete;
    FatTreeExtraction &operator=(const FatTreeExtraction &) = delete;
    const json::Value &definition() const;
    const std::string &digest() const;
    json::Value execute(const FatTreeExtractionGrant &, const FatTreeExtractionHooks &);
};
} // namespace disked
