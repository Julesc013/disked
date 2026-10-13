#pragma once
#include "runtime/command/json.h"
#include <memory>

namespace disked {
namespace evidence {
namespace proposal {
struct FatTreeHistoryBudget {
    std::uint64_t bytes = 1073741824;
    std::size_t records = 2000000, entries = 65536;
};
struct FatTreeHistoryError : std::runtime_error {
    explicit FatTreeHistoryError(const char *code) : std::runtime_error(code) {
    }
};
// Private supplied-byte inspection. Never opens recorded paths or grants effects.
// Retains bounded per-entry state and one incomplete line, not the complete ledger.
class FatTreeHistory final {
    struct Impl;
    std::unique_ptr<Impl> impl_;

  public:
    explicit FatTreeHistory(const FatTreeHistoryBudget & = FatTreeHistoryBudget{});
    ~FatTreeHistory();
    FatTreeHistory(const FatTreeHistory &) = delete;
    FatTreeHistory &operator=(const FatTreeHistory &) = delete;
    void consume(const std::string &bytes);
    json::Value finish();
};
} // namespace proposal
} // namespace evidence
} // namespace disked
