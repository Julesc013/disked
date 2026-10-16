#include "portable/exfat/exfat.h"
#include "runtime/command/json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
static void need(bool value) {
    if (!value)
        throw std::runtime_error("exFAT directory probe invariant");
}
static const V &field(const V &v, const char *k) {
    auto p = v.find(k);
    need(p != nullptr);
    return *p;
}
static de_u32 small(const V &v) {
    de_u64 n{};
    de_u32 out = 0;
    need(v.kind == V::Kind::string && !de_u64_parse(v.text.data(), v.text.size(), &n) &&
         !de_u64_to_u32(&n, &out));
    return out;
}
static V number(de_u32 n) {
    return V::number(std::to_string(n));
}
static V decimal(const de_u64 &n) {
    char bytes[21];
    need(!de_u64_format(&n, bytes, sizeof(bytes)));
    return V::string(bytes);
}
static std::vector<unsigned char> unhex(const V &v) {
    need(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 16386);
    std::vector<unsigned char> result(v.text.size() / 2);
    for (std::size_t i = 0; i < v.text.size(); ++i) {
        const auto c = v.text[i];
        const auto d = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : 99;
        need(d < 16);
        result[i / 2] = static_cast<unsigned char>((result[i / 2] << 4) | d);
    }
    return result;
}
static V units(const unsigned short *p, unsigned int count) {
    auto result = V::array();
    for (unsigned int i = 0; i < count; ++i)
        result.items.push_back(number(p[i]));
    return result;
}
static std::string hex(de_view view) {
    static const char digits[] = "0123456789abcdef";
    std::string result;
    for (std::size_t i = 0; i < view.size; ++i) {
        result += digits[view.data[i] >> 4];
        result += digits[view.data[i] & 15];
    }
    return result;
}
static V time_value(const de_exfat_time &t) {
    auto v = V::object();
    v.put("raw", number(t.raw))
        .put("fraction", number(t.fraction))
        .put("offset", number(t.offset))
        .put("valid", V::boolean_value(t.valid != 0))
        .put("offset_known", V::boolean_value(t.offset_known != 0))
        .put("offset_minutes", V::number(std::to_string(t.offset_minutes)))
        .put("year", number(t.year))
        .put("month", number(t.month))
        .put("day", number(t.day))
        .put("hour", number(t.hour))
        .put("minute", number(t.minute))
        .put("second", number(t.second));
    return v;
}
static V observe(const V &row) {
    auto bytes = unhex(field(row, "bytes"));
    const auto before = bytes;
    de_view view{bytes.data(), bytes.size()};
    auto out = V::object();
    if (field(row, "op").text == "slot") {
        de_exfat_slot v;
        std::memset(&v, 0xa5, sizeof(v));
        unsigned char saved[sizeof(v)];
        std::memcpy(saved, &v, sizeof(v));
        const auto code = de_exfat_slot_read(&view, &v);
        out.put("status", number(code));
        if (code)
            need(!std::memcmp(saved, &v, sizeof(v)));
        else {
            need(v.raw.data == view.data && v.raw.size == view.size);
            out.put("raw", V::string(hex(v.raw)))
                .put("kind", number(v.kind))
                .put("type", number(v.type))
                .put("issues", number(v.issues))
                .put("in_use", V::boolean_value(v.in_use != 0))
                .put("secondary", V::boolean_value(v.secondary != 0))
                .put("benign", V::boolean_value(v.benign != 0))
                .put("first_cluster", number(v.first_cluster))
                .put("data_length", decimal(v.data_length))
                .put("unit_count", number(v.unit_count))
                .put("units", units(v.units, v.kind == DE_EXFAT_DIR_LABEL  ? 11U
                                             : v.kind == DE_EXFAT_DIR_NAME ? 15U
                                                                           : 0U));
        }
    } else {
        need(field(row, "op").text == "set");
        de_exfat_file_set v;
        std::memset(&v, 0xa5, sizeof(v));
        unsigned char saved[sizeof(v)];
        std::memcpy(saved, &v, sizeof(v));
        const auto code =
            de_exfat_file_set_read(&view, small(field(row, "clusters")), small(field(row, "shift")),
                                   small(field(row, "budget")), &v);
        out.put("status", number(code));
        if (code)
            need(!std::memcmp(saved, &v, sizeof(v)));
        else {
            need(v.raw.data == view.data && v.raw.size <= view.size);
            out.put("raw", V::string(hex(v.raw)));
#define N(k) out.put(#k, number(v.k))
            N(issues);
            N(attributes);
            N(stream_flags);
            N(first_cluster);
            N(secondary_count);
            N(declared_bytes);
            N(present_bytes);
            N(name_length);
            N(name_units_present);
            N(benign_extensions);
            N(unsupported_extensions);
            N(stored_checksum);
            N(calculated_checksum);
            N(name_hash);
#undef N
#define B(k) out.put(#k, V::boolean_value(v.k != 0))
            B(primary_present);
            B(stream_present);
            B(complete);
            B(checksum_valid);
            B(associated);
            B(encoding_valid);
            B(name_characters_valid);
            B(stream_valid);
            B(metadata_valid);
#undef B
            out.put("units", units(v.units, v.name_units_present))
                .put("data_length", decimal(v.data_length))
                .put("valid_data_length", decimal(v.valid_data_length))
                .put("created", time_value(v.created))
                .put("modified", time_value(v.modified))
                .put("accessed", time_value(v.accessed));
        }
    }
    need(bytes == before);
    return out;
}
static int guard() {
    auto *memory = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, 16384, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    need(memory != nullptr);
    DWORD old = 0;
    auto *end = memory + 8192;
    need(VirtualProtect(end, 4096, PAGE_NOACCESS, &old) != 0);
    de_exfat_file_set value{};
    unsigned char saved[sizeof(value)];
    std::memcpy(saved, &value, sizeof(value));
    de_view empty{nullptr, 0}, invalid{nullptr, 1}, large{end, 8193};
    need(de_exfat_file_set_read(nullptr, 10, 9, 8192, &value) == DE_INVALID);
    need(de_exfat_file_set_read(&invalid, 10, 9, 8192, &value) == DE_INVALID);
    need(de_exfat_file_set_read(&empty, 10, 9, 8192, nullptr) == DE_INVALID);
    need(de_exfat_file_set_read(&large, 10, 9, 8193, &value) == DE_BOUNDS);
    need(!std::memcmp(saved, &value, sizeof(value)));
    for (std::size_t size = 0; size <= 96; ++size) {
        auto *start = end - size;
        std::memset(start, 0, size);
        if (size >= 32) {
            start[0] = 0x85;
            start[1] = 2;
        }
        if (size >= 64) {
            start[32] = 0xc0;
            start[35] = 1;
        }
        de_view view{start, size};
        need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
        need(de_exfat_file_set_read(&view, 10, 9, size, &value) == DE_OK);
        if (size) {
            std::memcpy(saved, &value, sizeof(value));
            need(de_exfat_file_set_read(&view, 10, 9, size - 1, &value) == DE_BOUNDS);
            need(!std::memcmp(saved, &value, sizeof(value)));
        }
        need(VirtualProtect(memory, 8192, PAGE_READWRITE, &old) != 0);
    }
    for (auto size : {static_cast<std::size_t>(8191), static_cast<std::size_t>(8192)}) {
        auto *start = end - size;
        std::memset(start, 0, size);
        start[0] = 0x85;
        start[1] = 255;
        start[32] = 0xc0;
        start[35] = 1;
        start[64] = 0xc1;
        de_view view{start, size};
        need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
        need(de_exfat_file_set_read(&view, 10, 9, size, &value) == DE_OK);
        need(VirtualProtect(memory, 8192, PAGE_READWRITE, &old) != 0);
    }
    de_exfat_slot slot{};
    unsigned char slot_saved[sizeof(slot)];
    std::memcpy(slot_saved, &slot, sizeof(slot));
    for (std::size_t n = 0; n < 32; ++n) {
        de_view view{end - n, n};
        need(de_exfat_slot_read(&view, &slot) == DE_BOUNDS);
        need(!std::memcmp(slot_saved, &slot, sizeof(slot)));
    }
    de_view exact{end - 32, 32};
    need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
    need(de_exfat_slot_read(&exact, &slot) == DE_OK);
    need(VirtualFree(memory, 0, MEM_RELEASE) != 0);
    std::cout << "guard passed\n";
    return 0;
}
int main(int argc, char **argv) {
    try {
        if (argc == 2 && !std::strcmp(argv[1], "--guard"))
            return guard();
        std::string bytes((std::istreambuf_iterator<char>(std::cin)), {});
        disked::json::Limits limits;
        limits.bytes = 8 * 1024 * 1024;
        limits.values = 600000;
        limits.string_bytes = 20000;
        auto input = disked::json::parse(bytes, limits);
        auto output = V::array();
        for (const auto &row : input.items)
            output.items.push_back(observe(row));
        std::cout << disked::json::dump(output, limits) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 20;
    }
}
