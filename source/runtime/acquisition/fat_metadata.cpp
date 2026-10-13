#include "fat_metadata.h"
#include "portable/fat/fat.h"
#include <algorithm>

namespace disked {
namespace {
using V = json::Value;
using Units = std::vector<std::uint16_t>;
using Bytes = std::vector<unsigned char>;
void require(bool valid, const char *code) {
    if (!valid)
        throw FatMetadataError(code);
}
V exact(std::uint64_t value) {
    return V::string(std::to_string(value));
}
std::string hex(const unsigned char *data, std::size_t size) {
    const char digits[] = "0123456789abcdef";
    std::string result;
    for (std::size_t i = 0; i < size; ++i) {
        result += digits[data[i] >> 4];
        result += digits[data[i] & 15];
    }
    return result;
}
V units_value(const Units &units) {
    auto result = V::array();
    for (const auto unit : units)
        result.items.push_back(exact(unit));
    return result;
}
bool valid_utf16(const Units &units) {
    for (std::size_t i = 0; i < units.size(); ++i) {
        const auto unit = units[i];
        if (unit >= 0xd800 && unit <= 0xdbff) {
            if (++i == units.size() || units[i] < 0xdc00 || units[i] > 0xdfff)
                return false;
        } else if (unit >= 0xdc00 && unit <= 0xdfff)
            return false;
    }
    return true;
}
std::string utf8(const Units &units) {
    std::string text;
    for (std::size_t i = 0; i < units.size(); ++i) {
        std::uint32_t point = units[i];
        if (point >= 0xd800 && point <= 0xdbff) {
            const auto low = units[++i];
            point = 0x10000 + ((point - 0xd800) << 10) + (low - 0xdc00);
        }
        if (point < 0x80)
            text += static_cast<char>(point);
        else if (point < 0x800) {
            text += static_cast<char>(0xc0 | (point >> 6));
            text += static_cast<char>(0x80 | (point & 63));
        } else if (point < 0x10000) {
            text += static_cast<char>(0xe0 | (point >> 12));
            text += static_cast<char>(0x80 | ((point >> 6) & 63));
            text += static_cast<char>(0x80 | (point & 63));
        } else {
            text += static_cast<char>(0xf0 | (point >> 18));
            text += static_cast<char>(0x80 | ((point >> 12) & 63));
            text += static_cast<char>(0x80 | ((point >> 6) & 63));
            text += static_cast<char>(0x80 | (point & 63));
        }
    }
    return text;
}
const char *component_issue(const Units &units) {
    if (units.empty() || units.size() > 255)
        return "fat_metadata_name_length";
    if (!valid_utf16(units))
        return "fat_metadata_name_utf16";
    if (units.back() == '.' || units.back() == ' ')
        return "fat_metadata_name_trailing";
    std::string base;
    bool in_base = true;
    for (const auto unit : units) {
        if (unit < 32 || unit == 127 || unit == '/' || unit == '\\' || unit == ':' || unit == '*' ||
            unit == '?' || unit == '"' || unit == '<' || unit == '>' || unit == '|')
            return "fat_metadata_name_character";
        if (unit == '.')
            in_base = false;
        if (in_base) {
            if (unit == 0x00b9 || unit == 0x00b2 || unit == 0x00b3)
                base += unit == 0x00b9 ? '1' : unit == 0x00b2 ? '2' : '3';
            else if (unit >= 'a' && unit <= 'z')
                base += static_cast<char>(unit - 'a' + 'A');
            else
                base += unit < 128 ? static_cast<char>(unit) : '_';
        }
    }
    while (!base.empty() && base.back() == ' ')
        base.pop_back();
    if (base == "CON" || base == "PRN" || base == "AUX" || base == "NUL" || base == "CONIN$" ||
        base == "CONOUT$" ||
        (base.size() == 4 && (base.substr(0, 3) == "COM" || base.substr(0, 3) == "LPT") &&
         base[3] >= '1' && base[3] <= '9'))
        return "fat_metadata_name_reserved";
    return nullptr;
}
void validate_policy(const FatMetadataPolicy &p) {
    require(p.name_selection == "long_or_short" || p.name_selection == "short" ||
                p.name_selection == "identity",
            "fat_metadata_policy_name");
    require(p.unrepresentable_name == "refuse" || p.unrepresentable_name == "identity",
            "fat_metadata_policy_unrepresentable");
    require(p.time_interpretation == "preserve_raw" || p.time_interpretation == "fixed_offset",
            "fat_metadata_policy_time");
    require(p.utc_offset_minutes >= -840 && p.utc_offset_minutes <= 840 &&
                (p.time_interpretation != "preserve_raw" || !p.utc_offset_minutes),
            "fat_metadata_policy_offset");
}
Units short_part(Bytes bytes, bool lowercase, const FatMetadataPolicy &policy,
                 const FatOemDecoder &decode) {
    while (!bytes.empty() && bytes.back() == ' ')
        bytes.pop_back();
    if (bytes.empty())
        return {};
    for (const auto byte : bytes)
        require(byte >= 32 && byte != 127 && byte != ' ' && byte != '.',
                "fat_metadata_short_encoding");
    require(policy.oem_code_page && decode, "fat_metadata_oem_required");
    auto result = decode(policy.oem_code_page, bytes);
    require(!result.empty() && result.size() <= 255 && valid_utf16(result),
            "fat_metadata_oem_result");
    // An explicit decoder cannot silently reinterpret the invariant ASCII set.
    if (std::all_of(bytes.begin(), bytes.end(), [](unsigned char b) { return b < 128; })) {
        require(result.size() == bytes.size(), "fat_metadata_oem_result");
        for (std::size_t i = 0; i < bytes.size(); ++i)
            require(result[i] == bytes[i], "fat_metadata_oem_result");
    }
    if (lowercase) {
        for (auto &unit : result) {
            require(unit < 128, "fat_metadata_non_ascii_case");
            if (unit >= 'A' && unit <= 'Z')
                unit = static_cast<std::uint16_t>(unit - 'A' + 'a');
        }
    }
    return result;
}
bool leap(unsigned year) {
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}
unsigned month_days(unsigned year, unsigned month) {
    const unsigned days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return days[month - 1] + (month == 2 && leap(year) ? 1U : 0U);
}
V time_candidate(unsigned date, unsigned time, unsigned fraction, const FatMetadataPolicy &policy,
                 const char *precision) {
    auto result = V::object()
                      .put("raw_date", exact(date))
                      .put("raw_time", exact(time))
                      .put("raw_fraction", exact(fraction))
                      .put("precision", V::string(precision));
    const unsigned year = 1980 + (date >> 9), month = (date >> 5) & 15, day = date & 31;
    const unsigned hour = time >> 11, minute = (time >> 5) & 63, second = (time & 31) * 2;
    const char *reason = nullptr;
    if (!date)
        reason = "unspecified";
    else if (!month || month > 12 || !day || day > month_days(year, month) || hour > 23 ||
             minute > 59 || second > 58 || fraction > 199)
        reason = "invalid";
    else if (policy.time_interpretation == "preserve_raw")
        reason = "raw_only";
    if (reason)
        return result.put("status", V::string("unapplied"))
            .put("reason", V::string(reason))
            .put("filetime_candidate", V{});
    std::uint64_t days = 0;
    for (unsigned y = 1601; y < year; ++y)
        days += leap(y) ? 366 : 365;
    for (unsigned m = 1; m < month; ++m)
        days += month_days(year, m);
    days += day - 1;
    auto seconds = static_cast<std::int64_t>(days * 86400 + hour * 3600 + minute * 60 + second);
    seconds -= static_cast<std::int64_t>(policy.utc_offset_minutes) * 60;
    const auto ticks = static_cast<std::uint64_t>(seconds) * 10000000 + fraction * 100000ULL;
    return result.put("status", V::string("candidate"))
        .put("reason", V{})
        .put("filetime_candidate", exact(ticks));
}
} // namespace
V fat_metadata_policy_value(const FatMetadataPolicy &p) {
    validate_policy(p);
    return V::object()
        .put("name_selection", V::string(p.name_selection))
        .put("unrepresentable_name", V::string(p.unrepresentable_name))
        .put("oem_code_page", exact(p.oem_code_page))
        .put("time_interpretation", V::string(p.time_interpretation))
        .put("utc_offset_minutes", V::string(std::to_string(p.utc_offset_minutes)));
}
V fat_metadata_candidates(const FatMetadataInput &input, const FatMetadataPolicy &policy,
                          const FatOemDecoder &decode) {
    validate_policy(policy);
    require(input.bits == 12 || input.bits == 16 || input.bits == 32, "fat_metadata_bits");
    require(input.long_slots.size() <= 640 && input.long_slots.size() % 32 == 0,
            "fat_metadata_slots");
    const de_view raw{input.record.data(), input.record.size()};
    const de_view slots{input.long_slots.data(), input.long_slots.size()};
    de_fat_dirent entry{};
    require(!de_fat_dirent_read(&raw, input.bits, &entry), "fat_metadata_record");
    de_fat_lfn name{};
    require(!de_fat_lfn_read(&slots, &raw, input.bits, &name), "fat_metadata_slots");
    const Units original_units(name.units, name.units + name.unit_count);
    auto original = V::object()
                        .put("source_offset", exact(input.source_offset))
                        .put("raw_record", V::string(hex(raw.data, raw.size)))
                        .put("raw_oem_name", V::string(hex(raw.data, 11)))
                        .put("raw_long_slots", V::string(hex(slots.data, slots.size)))
                        .put("long_units", units_value(original_units))
                        .put("long_name_issues", exact(name.issues))
                        .put("entry_issues", exact(entry.issues))
                        .put("attributes", exact(entry.attributes))
                        .put("case_flags", exact(entry.case_flags));
    Units output;
    std::string basis;
    std::string issue;
    const bool live =
        (entry.kind == DE_FAT_DIRENT_FILE || entry.kind == DE_FAT_DIRENT_DIRECTORY) && !entry.dot &&
        !(entry.issues & (DE_FAT_DIR_ATTRIBUTES | DE_FAT_DIR_CLUSTER | DE_FAT_DIR_FILE_STATE));
    if (!live)
        issue = "fat_metadata_not_live";
    else if (policy.name_selection != "identity") {
        try {
            if (policy.name_selection == "long_or_short" && !input.long_slots.empty()) {
                require(name.associated && name.unicode_valid && name.canonical_name &&
                            !name.issues,
                        "fat_metadata_long_name");
                output.assign(name.units, name.units + name.name_length);
                basis = "long_name";
            } else {
                require(!(entry.issues & (DE_FAT_DIR_CASE | DE_FAT_DIR_NAME)),
                        "fat_metadata_short_name");
                Bytes base(input.record.begin(), input.record.begin() + 8);
                if (base.front() == 5)
                    base.front() = 0xe5;
                output = short_part(std::move(base), (entry.case_flags & 8) != 0, policy, decode);
                const auto extension =
                    short_part(Bytes(input.record.begin() + 8, input.record.begin() + 11),
                               (entry.case_flags & 16) != 0, policy, decode);
                if (!extension.empty()) {
                    output.push_back('.');
                    output.insert(output.end(), extension.begin(), extension.end());
                }
                basis = "short_name";
            }
            const auto *invalid = component_issue(output);
            issue = invalid ? invalid : "";
        } catch (const FatMetadataError &error) {
            issue = error.what();
        } catch (...) {
            issue = "fat_metadata_oem_error";
        }
    }
    if (live && (policy.name_selection == "identity" ||
                 (!issue.empty() && policy.unrepresentable_name == "identity"))) {
        const auto identity = "entry_" + std::to_string(input.source_offset);
        output.assign(identity.begin(), identity.end());
        basis = "synthetic_identity";
    }
    auto result = V::object()
                      .put("schema", V::string("org.disked.fat-metadata-candidates/1"))
                      .put("policy", fat_metadata_policy_value(policy))
                      .put("original", std::move(original))
                      .put("diagnostic", issue.empty() ? V{} : V::string(issue))
                      .put("authorizes_effects", V::boolean_value(false));
    if (!live || (!issue.empty() && policy.unrepresentable_name != "identity"))
        return result.put("status", V::string("refused"));
    return result.put("status", V::string("candidate"))
        .put("name", V::object()
                         .put("utf16_units", units_value(output))
                         .put("utf8", V::string(utf8(output)))
                         .put("basis", V::string(basis))
                         .put("matches_selected_original_name",
                              V::boolean_value(basis != "synthetic_identity")))
        .put("native_attributes_candidate", exact(entry.attributes & 0x27))
        .put("creation", time_candidate(entry.creation_date, entry.creation_time,
                                        entry.creation_fraction, policy, "10ms"))
        .put("write", time_candidate(entry.write_date, entry.write_time, 0, policy, "2s"))
        .put("access", time_candidate(entry.access_date, 0, 0, policy, "date_at_local_midnight"))
        .put("native_collision_checked", V::boolean_value(false))
        .put("native_metadata_applied", V::boolean_value(false));
}
} // namespace disked
