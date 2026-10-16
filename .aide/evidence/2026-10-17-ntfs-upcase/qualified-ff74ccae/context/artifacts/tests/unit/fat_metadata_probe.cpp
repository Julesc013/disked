#include "runtime/acquisition/fat_metadata.h"
#include <algorithm>
#include <iostream>

using V = disked::json::Value;
static std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw std::runtime_error("metadata_probe_field");
    return p->text;
}
static std::uint64_t integer(const V &v, const char *key, std::uint64_t fallback = 0) {
    const auto value = text(v, key, std::to_string(fallback));
    if (!disked::json::decimal_u64(value))
        throw std::runtime_error("metadata_probe_integer");
    return std::stoull(value);
}
static std::vector<unsigned char> unhex(const std::string &s) {
    if (s.size() % 2 || s.size() > 1280 || s.find_first_not_of("0123456789abcdef") != s.npos)
        throw std::runtime_error("metadata_probe_hex");
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
            unsigned calls = 0;
            try {
                disked::FatMetadataInput input;
                const auto bits = integer(v, "bits", 16);
                if (bits > 32)
                    throw disked::FatMetadataError("fat_metadata_bits");
                input.bits = static_cast<int>(bits);
                input.source_offset = integer(v, "source_offset", 512);
                const auto raw = unhex(text(v, "record"));
                if (raw.size() != input.record.size())
                    throw std::runtime_error("metadata_probe_record");
                std::copy(raw.begin(), raw.end(), input.record.begin());
                input.long_slots = unhex(text(v, "slots"));
                disked::FatMetadataPolicy policy;
                policy.name_selection = text(v, "name_selection", "long_or_short");
                policy.unrepresentable_name = text(v, "unrepresentable_name", "refuse");
                const auto page = integer(v, "oem_code_page", 437);
                if (page > UINT32_MAX)
                    throw std::runtime_error("metadata_probe_page");
                policy.oem_code_page = static_cast<std::uint32_t>(page);
                policy.time_interpretation = text(v, "time_interpretation", "preserve_raw");
                const auto offset = text(v, "utc_offset_minutes", "0");
                std::size_t used = 0;
                policy.utc_offset_minutes = std::stoi(offset, &used);
                if (used != offset.size())
                    throw std::runtime_error("metadata_probe_offset");
                disked::FatOemDecoder port;
                const auto fault = text(v, "decoder_fault");
                if (fault != "missing")
                    port = [&](std::uint32_t code_page, const std::vector<unsigned char> &bytes) {
                        ++calls;
                        if (fault == "throw")
                            throw std::runtime_error("decoder fault");
                        std::vector<std::uint16_t> units;
                        const auto *mapping = v.find("mapping");
                        if (code_page != 437 && code_page != 850)
                            throw disked::FatMetadataError("fat_metadata_oem_unqualified");
                        for (auto byte : bytes) {
                            if (byte < 128)
                                units.push_back(byte);
                            else if (mapping && mapping->find(std::to_string(byte))) {
                                const auto unit = integer(*mapping, std::to_string(byte).c_str());
                                if (unit > UINT16_MAX)
                                    throw std::runtime_error("metadata_probe_unit");
                                units.push_back(static_cast<std::uint16_t>(unit));
                            } else
                                throw disked::FatMetadataError("fat_metadata_oem_unqualified");
                        }
                        if (fault == "ascii_changed" && !units.empty())
                            units[0] = 'x';
                        if (fault == "surrogate")
                            units = {0xd800};
                        if (fault == "empty")
                            units.clear();
                        return units;
                    };
                out.put("value", disked::fat_metadata_candidates(input, policy, port));
            } catch (const disked::FatMetadataError &error) {
                out.put("error", V::string(error.what()));
            }
            out.put("decoder_calls", V::string(std::to_string(calls)));
            std::cout << disked::json::dump(out) << '\n' << std::flush;
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
