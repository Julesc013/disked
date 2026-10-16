#pragma once
#include "runtime/command/protocol.h"
#include <memory>
#include <mutex>

namespace disked {
class FatCaptureStore final {
    struct Entry {
        std::string request_id, sha256;
        std::shared_ptr<const std::string> bytes;
    };
    const std::function<std::string()> domain_source_;
    mutable std::mutex mutex_;
    std::string domain_;
    std::uint64_t sequence_ = 0;
    std::map<std::string, Entry> entries_;

  public:
    explicit FatCaptureStore(std::function<std::string()> domain_source);
    std::string reserve(const std::string &request_id);
    json::Value commit(const std::string &capture_id, const json::Value &record);
    void abandon(const std::string &capture_id) noexcept;
    json::Value list() const;
    json::Value read(const std::string &capture_id, std::uint64_t offset,
                     std::uint64_t bytes) const;
    json::Value release(const std::string &capture_id);
    static constexpr std::size_t slots = 4, record_bytes = 8 * 1024 * 1024, chunk_bytes = 196608;
};
// Store errors are finite refusals; unexpected exceptions retain failed4 semantics.
class FatRetentionError : public std::runtime_error {
  public:
    explicit FatRetentionError(const char *code) : std::runtime_error(code) {
    }
};
Outcome dispatch_fat_capture(const std::string &, const std::string &, const json::Value &,
                             FatCaptureStore &);
} // namespace disked
