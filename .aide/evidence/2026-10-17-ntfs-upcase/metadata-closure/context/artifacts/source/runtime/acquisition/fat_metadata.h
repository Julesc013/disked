#pragma once
#include "runtime/command/json.h"
#include <array>
#include <cstdint>
#include <functional>
#include <vector>

namespace disked {
struct FatMetadataPolicy {
    std::string name_selection = "long_or_short";
    std::string unrepresentable_name = "refuse";
    std::uint32_t oem_code_page = 0;
    std::string time_interpretation = "preserve_raw";
    int utc_offset_minutes = 0;
};
struct FatMetadataInput {
    int bits = 0;
    std::uint64_t source_offset = 0;
    std::array<unsigned char, 32> record{};
    std::vector<unsigned char> long_slots;
};
// Supplied strict OEM decoding; no host conversion or implicit active code page.
// The concrete adapter must reject best-fit/replacement and qualify its decoder.
using FatOemDecoder =
    std::function<std::vector<std::uint16_t>(std::uint32_t, const std::vector<unsigned char> &)>;
struct FatMetadataError : std::runtime_error {
    explicit FatMetadataError(const char *code) : std::runtime_error(code) {
    }
};
// Pure bounded mapping. Reparses exact original records/slots, preserves them,
// and returns native name/time/attribute candidates or explicit unapplied facts.
// No source membership, native collision proof or effect authority is created.
json::Value fat_metadata_candidates(const FatMetadataInput &, const FatMetadataPolicy &,
                                    const FatOemDecoder & = {});
json::Value fat_metadata_policy_value(const FatMetadataPolicy &);
} // namespace disked
