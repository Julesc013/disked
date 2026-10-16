#pragma once
#include "runtime/acquisition/fat_metadata.h"

namespace disked {
// Private Windows output-name decoder for explicitly selected CP437/CP850.
// Rejects replacement/best-fit and requires an exact byte roundtrip.
std::vector<std::uint16_t> fat_decode_oem_windows(std::uint32_t code_page,
                                                  const std::vector<unsigned char> &bytes);
json::Value fat_native_metadata_candidates(const FatMetadataInput &, const FatMetadataPolicy &);
} // namespace disked
