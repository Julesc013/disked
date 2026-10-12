#pragma once
#include "runtime/command/json.h"
#include <array>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace disked {
// Withdraw derived applicability while preserving original entries and measured matches.
void withdraw_fat_namespace_applicability(json::Value &, const char *diagnostic);
using FatNameUnits = std::vector<std::uint16_t>;
enum class FatNameState { Known, Rejected, Unknown };
enum class FatNameEquality { Equal, Different, Unknown };
struct FatNameAssessment {
    FatNameState state = FatNameState::Unknown;
    std::string reason;
};
struct FatNameDecode {
    FatNameAssessment assessment;
    FatNameUnits units;
};
// Local comparison port; provider lifetime covers the call. This is not a plugin
// loader, source identity or storage-consumer admission contract.
struct FatNameConsumer {
    std::string id;
    json::Value binding = json::Value::object();
    std::function<FatNameDecode(const std::array<unsigned char, 11> &)> decode_short;
    std::function<FatNameAssessment(const FatNameUnits &)> component;
    std::function<FatNameEquality(const FatNameUnits &, const FatNameUnits &)> equal;
};
enum class FatNamespaceKind { File, Directory, Excluded, Unknown };
struct FatNamespaceEntry {
    std::size_t id = 0, parent = 0;
    std::uint64_t source_record_offset = 0;
    FatNamespaceKind kind = FatNamespaceKind::Unknown;
    std::array<unsigned char, 11> short_name{};
    bool has_long_name = false, long_associated = false, long_unicode_valid = false,
         long_canonical = false;
    FatNameUnits long_name;
};
struct FatNamespaceDirectory {
    std::size_t id = 0;
    bool records_complete = false;
};
struct FatNameQuery {
    std::size_t directory = 0;
    FatNameUnits component;
};
struct FatNamespaceLimits {
    std::size_t comparisons = 65536, findings = 128, output_bytes = 524288;
};
void validate_fat_name_consumer(const FatNameConsumer &);
void validate_fat_name_queries(const std::vector<FatNameQuery> &);
// Capture-local IDs and name-rule observations only; never opens or resolves a path.
json::Value observe_fat_namespace(const std::vector<FatNamespaceDirectory> &,
                                  const std::vector<FatNamespaceEntry> &, const FatNameConsumer &,
                                  const std::vector<FatNameQuery> &,
                                  const FatNamespaceLimits & = FatNamespaceLimits{},
                                  bool capture_applicable = true);
} // namespace disked
