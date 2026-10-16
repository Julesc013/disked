#include "file_names.h"
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <stdexcept>

namespace disked {
namespace {
using V = json::Value;
bool utf16(const FatNameUnits &units) {
    for (std::size_t i = 0; i < units.size(); ++i) {
        const auto u = units[i];
        if (u >= 0xd800 && u <= 0xdbff) {
            if (++i == units.size() || units[i] < 0xdc00 || units[i] > 0xdfff)
                return false;
        } else if (u >= 0xdc00 && u <= 0xdfff)
            return false;
    }
    return true;
}
std::uint16_t upper_ascii(std::uint16_t u) {
    return u >= 'a' && u <= 'z' ? static_cast<std::uint16_t>(u - 'a' + 'A') : u;
}
FatNameAssessment component(const FatNameUnits &name) {
    auto reject = [](const char *code) { return FatNameAssessment{FatNameState::Rejected, code}; };
    if (name.empty() || name.size() > 255 || !utf16(name))
        return reject("component_encoding_or_length");
    if (name.front() == ' ' || name.back() == ' ' || name.back() == '.')
        return reject("component_edge_space_or_dot");
    for (auto u : name)
        if (u < 32 || u == '<' || u == '>' || u == ':' || u == '"' || u == '/' || u == '\\' ||
            u == '|' || u == '?' || u == '*')
            return reject("component_reserved_character");
    FatNameUnits stem;
    for (auto u : name) {
        if (u == '.')
            break;
        stem.push_back(upper_ascii(u));
    }
    const auto ascii = [&](const char *text) {
        if (stem.size() != std::char_traits<char>::length(text))
            return false;
        for (std::size_t i = 0; i < stem.size(); ++i)
            if (stem[i] != static_cast<unsigned char>(text[i]))
                return false;
        return true;
    };
    if (ascii("CON") || ascii("PRN") || ascii("AUX") || ascii("NUL") || ascii("CONIN$") ||
        ascii("CONOUT$"))
        return reject("component_reserved_device");
    if (stem.size() == 4 &&
        ((stem[0] == 'C' && stem[1] == 'O' && stem[2] == 'M') ||
         (stem[0] == 'L' && stem[1] == 'P' && stem[2] == 'T')) &&
        ((stem[3] >= '1' && stem[3] <= '9') || stem[3] == 0xb9 || stem[3] == 0xb2 ||
         stem[3] == 0xb3))
        return reject("component_reserved_device");
    return {FatNameState::Known, "component_eligible"};
}
FatNameDecode decode(std::uint32_t page, const std::array<unsigned char, 11> &stored) {
    FatNameDecode out;
    out.assessment = {FatNameState::Rejected, "short_encoding_or_shape"};
    auto bytes = stored;
    if (bytes[0] == 5)
        bytes[0] = 0xe5;
    auto part = [&](std::size_t at, std::size_t width, FatNameUnits &units) {
        while (width && bytes[at + width - 1] == ' ')
            --width;
        if (!width)
            return true;
        WCHAR text[16]{};
        const auto n = MultiByteToWideChar(page, MB_ERR_INVALID_CHARS,
                                           reinterpret_cast<const char *>(bytes.data() + at),
                                           static_cast<int>(width), text, 16);
        if (!n)
            return false;
        for (int i = 0; i < n; ++i) {
            const auto u = static_cast<std::uint16_t>(text[i]);
            if (u <= 32 || u == '.' || u == '+' || u == ',' || u == ';' || u == '=' || u == '[' ||
                u == ']')
                return false;
            units.push_back(u);
        }
        return true;
    };
    FatNameUnits base, ext;
    if (!part(0, 8, base) || base.empty() || !part(8, 3, ext))
        return out;
    out.units = base;
    if (!ext.empty()) {
        out.units.push_back('.');
        out.units.insert(out.units.end(), ext.begin(), ext.end());
    }
    out.assessment = {FatNameState::Known, "short_decoded"};
    return out;
}
FatNameEquality equal(const FatNameUnits &a, const FatNameUnits &b) {
    if (a.empty() || b.empty() || a.size() > 255 || b.size() > 255 || !utf16(a) || !utf16(b))
        return FatNameEquality::Unknown;
    std::vector<WCHAR> left, right;
    for (auto u : a)
        left.push_back(static_cast<WCHAR>(u));
    for (auto u : b)
        right.push_back(static_cast<WCHAR>(u));
    const auto result = CompareStringOrdinal(left.data(), static_cast<int>(left.size()),
                                             right.data(), static_cast<int>(right.size()), TRUE);
    return result == CSTR_EQUAL                                        ? FatNameEquality::Equal
           : (result == CSTR_LESS_THAN || result == CSTR_GREATER_THAN) ? FatNameEquality::Different
                                                                       : FatNameEquality::Unknown;
}
} // namespace
FatNameConsumer windows_fat_name_consumer(std::uint32_t page) {
    if (page != 437 && page != 850 && page != 932)
        throw std::invalid_argument("fat_name_code_page");
    CPINFOEXW info{};
    if (!GetCPInfoExW(page, 0, &info))
        throw std::runtime_error("fat_name_code_page_unavailable");
    FatNameConsumer out;
    out.id = "windows-ordinal-oem-" + std::to_string(page) + "/1";
    auto leads = V::array();
    for (auto c : info.LeadByte)
        leads.items.push_back(V::string(std::to_string(c)));
    out.binding = V::object()
                      .put("code_page", V::string(std::to_string(page)))
                      .put("max_char_bytes", V::string(std::to_string(info.MaxCharSize)))
                      .put("lead_byte_ranges", std::move(leads))
                      .put("comparison", V::string("CompareStringOrdinal(ignoreCase=true)"))
                      .put("conversion", V::string("MultiByteToWideChar(MB_ERR_INVALID_CHARS)"))
                      .put("scope", V::string("current-host text APIs and component-rule model"))
                      .put("normalization", V::string("none"))
                      .put("storage_consumer_qualified", V::boolean_value(false));
    out.decode_short = [page](const std::array<unsigned char, 11> &name) {
        return decode(page, name);
    };
    out.component = component;
    out.equal = equal;
    return out;
}
} // namespace disked
