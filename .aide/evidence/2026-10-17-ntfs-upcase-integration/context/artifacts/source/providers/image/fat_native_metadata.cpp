#include "fat_native_metadata.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace disked {
std::vector<std::uint16_t> fat_decode_oem_windows(std::uint32_t page,
                                                  const std::vector<unsigned char> &bytes) {
    if (page != 437 && page != 850)
        throw FatMetadataError("fat_metadata_oem_unqualified");
    if (bytes.empty() || bytes.size() > 11)
        throw FatMetadataError("fat_metadata_oem_bounds");
    const auto count = static_cast<int>(bytes.size());
    const auto *raw = reinterpret_cast<const char *>(bytes.data());
    wchar_t units[11]{};
    const auto converted = MultiByteToWideChar(page, MB_ERR_INVALID_CHARS, raw, count, units, 11);
    if (converted <= 0 || converted > 11)
        throw FatMetadataError("fat_metadata_oem_conversion");
    char returned[11]{};
    BOOL substituted = FALSE;
    const auto size = WideCharToMultiByte(page, WC_NO_BEST_FIT_CHARS, units, converted, returned,
                                          11, nullptr, &substituted);
    if (size != count || substituted)
        throw FatMetadataError("fat_metadata_oem_roundtrip");
    for (int i = 0; i < count; ++i)
        if (static_cast<unsigned char>(returned[i]) != bytes[static_cast<std::size_t>(i)])
            throw FatMetadataError("fat_metadata_oem_roundtrip");
    return std::vector<std::uint16_t>(units, units + converted);
}
json::Value fat_native_metadata_candidates(const FatMetadataInput &input,
                                           const FatMetadataPolicy &policy) {
    return fat_metadata_candidates(input, policy, fat_decode_oem_windows);
}
} // namespace disked
