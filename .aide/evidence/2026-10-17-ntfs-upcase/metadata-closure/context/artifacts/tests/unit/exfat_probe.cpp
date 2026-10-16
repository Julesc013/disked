#include "portable/exfat/exfat.h"
#include "runtime/command/json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
static void need(bool v) {
    if (!v)
        throw std::runtime_error("exfat probe invariant");
}
static const V &field(const V &v, const char *k) {
    auto p = v.find(k);
    need(p != nullptr);
    return *p;
}
static de_u64 exact(const V &v) {
    de_u64 n{};
    need(v.kind == V::Kind::string && !de_u64_parse(v.text.data(), v.text.size(), &n));
    return n;
}
static de_u32 small(const V &v) {
    auto n = exact(v);
    de_u32 out = 0;
    need(!de_u64_to_u32(&n, &out));
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
    need(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 98306);
    std::vector<unsigned char> bytes(v.text.size() / 2);
    for (std::size_t i = 0; i < v.text.size(); ++i) {
        char c = v.text[i];
        unsigned digit = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : 99;
        need(digit < 16);
        bytes[i / 2] = static_cast<unsigned char>((bytes[i / 2] << 4) | digit);
    }
    return bytes;
}
static V observe(const V &request) {
    auto bytes = unhex(field(request, "bytes"));
    const auto before = bytes;
    de_view view{bytes.data(), bytes.size()};
    auto result = V::object();
    const auto op = field(request, "op").text;
    if (op == "boot") {
        auto available = exact(field(request, "available"));
        de_exfat_boot value;
        std::memset(&value, 0xa5, sizeof(value));
        unsigned char saved[sizeof(value)];
        std::memcpy(saved, &value, sizeof(value));
        const auto code = de_exfat_boot_read(
            &view, &available, static_cast<int>(small(field(request, "backup"))), &value);
        result.put("status", number(code));
        if (code)
            need(std::memcmp(saved, &value, sizeof(value)) == 0);
        else {
#define N(k) result.put(#k, number(value.k))
            N(issues);
            N(fat_offset);
            N(fat_length);
            N(heap_offset);
            N(cluster_count);
            N(root_cluster);
            N(serial);
            N(revision);
            N(flags);
            N(sector_shift);
            N(cluster_shift);
            N(fat_count);
            N(drive_select);
            N(percent_in_use);
            N(sector_bytes);
            N(cluster_sectors);
            N(cluster_bytes);
            N(checksum);
            N(checksum_word);
            N(checksum_mismatches);
            N(active_fat);
#undef N
#define B(k) result.put(#k, V::boolean_value(value.k != 0))
            B(fields_present);
            B(complete_region);
            B(checksum_valid);
            B(usable_geometry);
            B(backup);
            B(mutable_fields_stale);
            B(texfat_structure);
            B(active_fat_known);
#undef B
#define D(k) result.put(#k, decimal(value.k))
            D(partition_offset);
            D(volume_sectors);
            D(volume_bytes);
            D(available_bytes);
            D(fat_bytes);
            D(heap_offset_bytes);
            D(heap_bytes);
#undef D
        }
    } else {
        need(op == "cell");
        de_exfat_cell value;
        std::memset(&value, 0xa5, sizeof(value));
        unsigned char saved[sizeof(value)];
        std::memcpy(saved, &value, sizeof(value));
        const auto code = de_exfat_cell_read(&view, small(field(request, "clusters")),
                                             small(field(request, "index")), &value);
        result.put("status", number(code));
        if (code)
            need(std::memcmp(saved, &value, sizeof(value)) == 0);
        else
            result.put("index", number(value.index))
                .put("value", number(value.value))
                .put("kind", number(value.kind));
    }
    need(before == bytes);
    return result;
}
static int guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    need(info.dwPageSize >= 4096);
    auto *memory = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, 65536, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    need(memory != nullptr);
    auto *end = memory + 49152;
    DWORD old = 0;
    need(VirtualProtect(end, 4096, PAGE_NOACCESS, &old) != 0);
    auto available = de_u64_from_u32(1048576);
    de_exfat_boot value{};
    unsigned char saved[sizeof(value)];
    std::memcpy(saved, &value, sizeof(value));
    de_view empty{nullptr, 0}, invalid{nullptr, 512};
    need(de_exfat_boot_read(nullptr, &available, 0, &value) == DE_INVALID);
    need(de_exfat_boot_read(&empty, nullptr, 0, &value) == DE_INVALID);
    need(de_exfat_boot_read(&empty, &available, 0, nullptr) == DE_INVALID);
    need(de_exfat_boot_read(&invalid, &available, 0, &value) == DE_INVALID);
    need(de_exfat_boot_read(&empty, &available, -1, &value) == DE_INVALID);
    need(std::memcmp(saved, &value, sizeof(value)) == 0);
    for (std::size_t size = 0; size < 512; ++size) {
        de_view view{end - size, size};
        need(!de_exfat_boot_read(&view, &available, 0, &value) &&
             value.issues == DE_EXFAT_TRUNCATED);
    }
    de_view too_large{end, 49153};
    std::memcpy(saved, &value, sizeof(value));
    need(de_exfat_boot_read(&too_large, &available, 0, &value) == DE_BOUNDS &&
         std::memcmp(saved, &value, sizeof(value)) == 0);
    for (unsigned shift = 9; shift <= 12; ++shift) {
        const auto bytes = static_cast<std::size_t>(12) << shift;
        auto *begin = end - bytes;
        std::memset(begin, 0, bytes);
        begin[108] = static_cast<unsigned char>(shift);
        for (auto size : {static_cast<std::size_t>(512), bytes - 1, bytes}) {
            auto *start = end - size;
            std::memset(start, 0, size);
            start[108] = static_cast<unsigned char>(shift);
            de_view view{start, size};
            need(VirtualProtect(memory, 49152, PAGE_READONLY, &old) != 0);
            need(!de_exfat_boot_read(&view, &available, 0, &value));
            need(VirtualProtect(memory, 49152, PAGE_READWRITE, &old) != 0);
        }
        de_view over{begin, bytes + 1};
        std::memcpy(saved, &value, sizeof(value));
        need(de_exfat_boot_read(&over, &available, 0, &value) == DE_BOUNDS &&
             std::memcmp(saved, &value, sizeof(value)) == 0);
    }
    de_exfat_cell cell{};
    unsigned char saved_cell[sizeof(cell)];
    std::memcpy(saved_cell, &cell, sizeof(cell));
    need(de_exfat_cell_read(nullptr, 10, 2, &cell) == DE_INVALID);
    need(de_exfat_cell_read(&empty, 10, 2, nullptr) == DE_INVALID);
    need(de_exfat_cell_read(&invalid, 10, 2, &cell) == DE_INVALID);
    need(std::memcmp(saved_cell, &cell, sizeof(cell)) == 0);
    for (std::size_t size = 0; size < 4; ++size) {
        de_view view{end - size, size};
        need(de_exfat_cell_read(&view, 10, 2, &cell) == DE_BOUNDS &&
             std::memcmp(saved_cell, &cell, sizeof(cell)) == 0);
    }
    de_view view{end - 4, 4};
    need(VirtualProtect(memory, 49152, PAGE_READONLY, &old) != 0);
    need(!de_exfat_cell_read(&view, 10, 2, &cell));
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
        limits.values = 50000;
        limits.string_bytes = 100000;
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
