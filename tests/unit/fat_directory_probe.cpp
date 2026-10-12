#include "portable/fat/fat.h"
#include "runtime/command/json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using V = disked::json::Value;
static void require(bool value) {
    if (!value)
        throw std::runtime_error("FAT directory probe invariant");
}
static const V &field(const V &value, const char *key) {
    const auto *item = value.find(key);
    require(item != nullptr);
    return *item;
}
static de_u32 small(const V &value) {
    de_u64 n{};
    de_u32 result = 0;
    require(value.kind == V::Kind::string &&
            !de_u64_parse(value.text.data(), value.text.size(), &n) && !de_u64_to_u32(&n, &result));
    return result;
}
static V number(unsigned long value) {
    return V::number(std::to_string(value));
}
static unsigned digit(char value) {
    if (value >= '0' && value <= '9')
        return static_cast<unsigned>(value - '0');
    if (value >= 'a' && value <= 'f')
        return static_cast<unsigned>(value - 'a' + 10);
    throw std::runtime_error("FAT directory hex");
}
static std::vector<unsigned char> unhex(const V &value) {
    require(value.kind == V::Kind::string && value.text.size() % 2 == 0 &&
            value.text.size() <= 4096);
    std::vector<unsigned char> result(value.text.size() / 2);
    for (std::size_t i = 0; i < result.size(); ++i)
        result[i] = static_cast<unsigned char>(digit(value.text[2 * i]) * 16 +
                                               digit(value.text[2 * i + 1]));
    return result;
}
static std::string hex(de_view value) {
    static const char digits[] = "0123456789abcdef";
    std::string result;
    for (std::size_t i = 0; i < value.size; ++i) {
        result += digits[value.data[i] >> 4];
        result += digits[value.data[i] & 15];
    }
    return result;
}
static V units(const unsigned short *data, std::size_t count) {
    auto result = V::array();
    for (std::size_t i = 0; i < count; ++i)
        result.items.push_back(number(data[i]));
    return result;
}
static V display(const unsigned short *data, std::size_t count, std::size_t capacity) {
    std::vector<char> output(capacity ? capacity : 1, 'Z');
    const auto before = output;
    auto status = de_fat_name_display(data, count, output.data(), capacity);
    auto result = V::object().put("status", number(static_cast<unsigned long>(status)));
    if (status)
        require(output == before);
    else
        result.put("text", V::string(output.data()));
    return result;
}
static V observe(const V &request) {
    const auto &op = field(request, "op");
    require(op.kind == V::Kind::string);
    if (op.text == "display") {
        const auto &values = field(request, "units");
        require(values.kind == V::Kind::array && values.items.size() <= 300);
        std::vector<unsigned short> data;
        for (const auto &value : values.items) {
            auto n = small(value);
            require(n <= 65535);
            data.push_back(static_cast<unsigned short>(n));
        }
        const auto before = data;
        auto capacity = small(field(request, "capacity"));
        require(capacity <= 2048);
        auto result = display(data.data(), data.size(), capacity);
        require(data == before);
        return result;
    }
    auto data = unhex(field(request, op.text == "checksum" ? "name" : "record"));
    const auto before = data;
    de_view record{data.data(), data.size()};
    auto result = V::object();
    if (op.text == "checksum") {
        unsigned char value = 0xa5;
        auto status = de_fat_short_checksum(&record, &value);
        result.put("status", number(static_cast<unsigned long>(status)));
        if (status)
            require(value == 0xa5);
        else
            result.put("checksum", number(value));
    } else {
        auto bits = small(field(request, "bits"));
        require(bits <= 64);
        if (op.text == "entry") {
            de_fat_dirent value;
            std::memset(&value, 0xa5, sizeof(value));
            unsigned char saved[sizeof(value)];
            std::memcpy(saved, &value, sizeof(value));
            auto status = de_fat_dirent_read(&record, static_cast<int>(bits), &value);
            result.put("status", number(static_cast<unsigned long>(status)));
            if (status)
                require(std::memcmp(saved, &value, sizeof(value)) == 0);
            else {
                result.put("kind", number(static_cast<unsigned long>(value.kind)))
                    .put("issues", number(value.issues))
                    .put("raw", V::string(hex(value.raw)))
                    .put("name_field", V::string(hex(value.name_field)))
                    .put("attributes", number(value.attributes))
                    .put("case_flags", number(value.case_flags))
                    .put("fraction", number(value.creation_fraction))
                    .put("raw_cluster", number(value.raw_cluster))
                    .put("cluster", number(value.cluster))
                    .put("file_bytes", number(value.file_bytes))
                    .put("dot", number(static_cast<unsigned long>(value.dot)))
                    .put("lead_escape", V::boolean_value(value.lead_byte_escape != 0))
                    .put("creation_time", number(value.creation_time))
                    .put("creation_date", number(value.creation_date))
                    .put("access_date", number(value.access_date))
                    .put("write_time", number(value.write_time))
                    .put("write_date", number(value.write_date))
                    .put("ordinal", number(value.ordinal))
                    .put("checksum", number(value.checksum))
                    .put("lfn_type", number(value.lfn_type))
                    .put("units", units(value.lfn_units, 13));
            }
        } else {
            require(op.text == "lfn");
            auto source = unhex(field(request, "slots"));
            const auto saved_source = source;
            de_view slots{source.data(), source.size()};
            de_fat_lfn value;
            std::memset(&value, 0xa5, sizeof(value));
            unsigned char saved[sizeof(value)];
            std::memcpy(saved, &value, sizeof(value));
            auto status = de_fat_lfn_read(&slots, &record, static_cast<int>(bits), &value);
            result.put("status", number(static_cast<unsigned long>(status)));
            if (status)
                require(std::memcmp(saved, &value, sizeof(value)) == 0);
            else {
                result.put("issues", number(value.issues))
                    .put("raw_slots", V::string(hex(value.raw_slots)))
                    .put("raw_short", V::string(hex(value.raw_short)))
                    .put("slots", number(static_cast<unsigned long>(value.slots)))
                    .put("unit_count", number(static_cast<unsigned long>(value.unit_count)))
                    .put("name_length", number(static_cast<unsigned long>(value.name_length)))
                    .put("units", units(value.units, value.unit_count))
                    .put("associated", V::boolean_value(value.associated != 0))
                    .put("unicode_valid", V::boolean_value(value.unicode_valid != 0))
                    .put("canonical", V::boolean_value(value.canonical_name != 0))
                    .put("terminated", V::boolean_value(value.terminated != 0))
                    .put("requires_escaping", V::boolean_value(value.requires_escaping != 0))
                    .put("display", display(value.units, value.name_length, 2048));
            }
            require(source == saved_source);
        }
    }
    require(data == before);
    return result;
}

static int guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    auto *pages = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, info.dwPageSize * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    require(pages != nullptr);
    auto *boundary = pages + info.dwPageSize;
    auto *raw = boundary - 32;
    std::memcpy(raw, "FILE    TXT", 11);
    raw[11] = 0x20;
    auto *long_boundary = pages + info.dwPageSize * 3;
    auto *long_records = long_boundary - 640;
    de_view stored_name{raw, 11};
    unsigned char checksum = 0;
    require(!de_fat_short_checksum(&stored_name, &checksum));
    const unsigned positions[13]{1, 3, 5, 7, 9, 14, 16, 18, 20, 22, 24, 28, 30};
    for (unsigned slot = 0; slot < 20; ++slot) {
        auto *row = long_records + slot * 32;
        row[0] = static_cast<unsigned char>((20 - slot) | (slot ? 0 : 64));
        row[11] = 15;
        row[13] = checksum;
        for (unsigned n = 0; n < 13; ++n) {
            const auto ordinal = (19 - slot) * 13 + n;
            const unsigned unit = ordinal < 255 ? 65 : (ordinal == 255 ? 0 : 65535);
            row[positions[n]] = static_cast<unsigned char>(unit & 255);
            row[positions[n] + 1] = static_cast<unsigned char>(unit >> 8);
        }
    }
    DWORD old = 0;
    require(VirtualProtect(pages, info.dwPageSize, PAGE_READONLY, &old) != 0);
    require(VirtualProtect(boundary, info.dwPageSize, PAGE_NOACCESS, &old) != 0);
    require(VirtualProtect(pages + info.dwPageSize * 2, info.dwPageSize, PAGE_READONLY, &old) != 0);
    require(VirtualProtect(long_boundary, info.dwPageSize, PAGE_NOACCESS, &old) != 0);
    for (int bits : {12, 16, 32}) {
        de_fat_dirent entry{};
        de_view view{raw, 32};
        require(!de_fat_dirent_read(&view, bits, &entry));
        for (std::size_t n = 0; n < 32; ++n) {
            de_view short_view{boundary - n, n};
            require(!de_fat_dirent_read(&short_view, bits, &entry) &&
                    entry.issues == DE_FAT_DIR_TRUNCATED);
        }
        de_view overlong{boundary, 33};
        unsigned char saved[sizeof(entry)];
        std::memcpy(saved, &entry, sizeof(entry));
        require(de_fat_dirent_read(&overlong, bits, &entry) == DE_BOUNDS &&
                std::memcmp(saved, &entry, sizeof(entry)) == 0);
        de_fat_lfn name{};
        de_view inaccessible{boundary, 641}, valid{raw, 32};
        de_view complete{long_records, 640};
        require(!de_fat_lfn_read(&complete, &valid, bits, &name) && name.associated &&
                name.name_length == 255 && name.unit_count == 260);
        unsigned char saved_name[sizeof(name)];
        std::memcpy(saved_name, &name, sizeof(name));
        require(de_fat_lfn_read(&inaccessible, &valid, bits, &name) == DE_BUFFER &&
                std::memcmp(saved_name, &name, sizeof(name)) == 0);
        for (std::size_t n : {1U, 2U, 31U, 33U, 63U, 639U}) {
            de_view partial{boundary - n, n};
            require(!de_fat_lfn_read(&partial, &valid, bits, &name) &&
                    name.issues == DE_FAT_LFN_TRUNCATED);
        }
    }
    char output[12];
    std::memset(output, 'Z', sizeof(output));
    require(de_fat_name_display(reinterpret_cast<unsigned short *>(boundary), 261, output,
                                sizeof(output)) == DE_BUFFER);
    require(de_fat_name_display(reinterpret_cast<unsigned short *>(boundary), 11, output, 11) ==
            DE_BUFFER);
    for (char ch : output)
        require(ch == 'Z');
    require(VirtualFree(pages, 0, MEM_RELEASE) != 0);
    std::puts("FAT directory protected records, bounded name sets and capacity-before-read checks "
              "passed.");
    return 0;
}

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--guard")
            return guard();
        require(argc == 1);
        disked::json::Limits limits;
        limits.bytes = 32768;
        limits.string_bytes = 8192;
        limits.values = 4096;
        std::string line;
        while (std::getline(std::cin, line)) {
            require(line.size() <= limits.bytes);
            std::cout << disked::json::dump(observe(disked::json::parse(line, limits)), limits)
                      << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
