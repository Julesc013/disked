#include "providers/image/fat_native_metadata.h"
#include <algorithm>
#include <iostream>

using V = disked::json::Value;
static std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw std::runtime_error("native_metadata_probe_field");
    return p->text;
}
static std::uint64_t integer(const V &v, const char *key, std::uint64_t fallback = 0) {
    const auto value = text(v, key, std::to_string(fallback));
    if (!disked::json::decimal_u64(value))
        throw std::runtime_error("native_metadata_probe_integer");
    return std::stoull(value);
}
static std::vector<unsigned char> unhex(const std::string &s) {
    if (s.size() % 2 || s.size() > 1280 || s.find_first_not_of("0123456789abcdef") != s.npos)
        throw std::runtime_error("native_metadata_probe_hex");
    std::vector<unsigned char> result;
    auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
    for (std::size_t i = 0; i < s.size(); i += 2)
        result.push_back(static_cast<unsigned char>(digit(s[i]) * 16 + digit(s[i + 1])));
    return result;
}
int main() {
    try {
        std::string line;
        while (std::getline(std::cin, line)) {
            const auto v = disked::json::parse(line);
            auto out = V::object();
            try {
                const auto page = integer(v, "oem_code_page", 437);
                if (page > UINT32_MAX)
                    throw std::runtime_error("native_metadata_probe_page");
                if (text(v, "kind") == "decode") {
                    auto units = V::array();
                    for (auto unit : disked::fat_decode_oem_windows(
                             static_cast<std::uint32_t>(page), unhex(text(v, "bytes"))))
                        units.items.push_back(V::string(std::to_string(unit)));
                    out.put("units", std::move(units));
                } else {
                    disked::FatMetadataInput input;
                    const auto bits = integer(v, "bits", 16);
                    if (bits > 32)
                        throw disked::FatMetadataError("fat_metadata_bits");
                    input.bits = static_cast<int>(bits);
                    input.source_offset = integer(v, "source_offset", 512);
                    const auto raw = unhex(text(v, "record"));
                    if (raw.size() != input.record.size())
                        throw std::runtime_error("native_metadata_probe_record");
                    std::copy(raw.begin(), raw.end(), input.record.begin());
                    input.long_slots = unhex(text(v, "slots"));
                    disked::FatMetadataPolicy policy;
                    policy.oem_code_page = static_cast<std::uint32_t>(page);
                    policy.name_selection = text(v, "name_selection", "long_or_short");
                    policy.unrepresentable_name = text(v, "unrepresentable_name", "refuse");
                    policy.time_interpretation = text(v, "time_interpretation", "preserve_raw");
                    const auto offset = text(v, "utc_offset_minutes", "0");
                    std::size_t used = 0;
                    policy.utc_offset_minutes = std::stoi(offset, &used);
                    if (used != offset.size())
                        throw std::runtime_error("native_metadata_probe_offset");
                    out.put("value", disked::fat_native_metadata_candidates(input, policy));
                }
            } catch (const disked::FatMetadataError &error) {
                out.put("error", V::string(error.what()));
            }
            std::cout << disked::json::dump(out) << '\n' << std::flush;
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
