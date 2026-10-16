#include "portable/fat/fat.h"
#include "runtime/command/json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <initializer_list>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
static void check(bool ok) {
    if (!ok)
        throw std::runtime_error("fat walk probe invariant");
}
static de_u32 field(const V &v, const char *name) {
    const auto *p = v.find(name);
    check(p && p->kind == V::Kind::number);
    de_u64 wide{};
    de_u32 small = 0;
    check(!de_u64_parse(p->text.data(), p->text.size(), &wide) && !de_u64_to_u32(&wide, &small));
    return small;
}
static V num(de_u32 n) {
    return V::number(std::to_string(n));
}
static V row(std::initializer_list<V> values) {
    auto v = V::array();
    v.items = values;
    return v;
}
static unsigned digit(char c) {
    check((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
}
static V observe(const V &v) {
    const auto bits = field(v, "bits"), clusters = field(v, "clusters");
    const auto start = field(v, "start"), page = field(v, "page");
    check(page && page <= 70000 && clusters <= 268435445);
    const auto *raw = v.find("fat");
    check(raw && raw->kind == V::Kind::string && raw->text.size() % 2 == 0);
    std::vector<unsigned char> fat(raw->text.size() / 2);
    for (std::size_t i = 0; i < fat.size(); ++i)
        fat[i] =
            static_cast<unsigned char>(digit(raw->text[i * 2]) * 16 + digit(raw->text[i * 2 + 1]));
    const auto before = fat;
    std::vector<unsigned char> seen(
        static_cast<std::size_t>(clusters / 8 + (clusters % 8 != 0)) + 9, 0xa5);
    de_fat_walk walk{};
    const auto status = de_fat_walk_init(static_cast<int>(bits), clusters, start, seen.data(),
                                         seen.size() - 9, &walk);
    auto result = V::object().put("status", V::number(std::to_string(status)));
    if (status)
        return result;
    auto steps = V::array(), pages = V::array();
    std::size_t calls = 0;
    while (walk.running) {
        const auto initial = walk.count;
        for (de_u32 i = 0; i < page && walk.running; ++i) {
            check(++calls <= 70000);
            de_fat_cell_request request{}, repeat{};
            const auto saved = walk;
            check(!de_fat_walk_request(&walk, &request) && !de_fat_walk_request(&walk, &repeat));
            check(!std::memcmp(&saved, &walk, sizeof(walk)) &&
                  !std::memcmp(&request, &repeat, sizeof(request)));
            std::size_t offset = 0;
            check(!de_u64_to_size(&request.offset, &offset));
            const auto available =
                offset < fat.size() ? std::min<std::size_t>(request.bytes, fat.size() - offset) : 0;
            de_view cell{available ? fat.data() + offset : nullptr, available};
            de_fat_walk_step step{};
            check(!de_fat_walk_feed(&walk, &cell, &step));
            steps.items.push_back(
                row({num(step.cluster), num(step.ordinal),
                     V::boolean_value(step.entry_present != 0), num(step.entry.raw_value),
                     num(step.entry.value), V::number(std::to_string(step.entry.kind))}));
        }
        pages.items.push_back(
            row({num(walk.count - initial), num(walk.count), V::boolean_value(walk.running != 0),
                 V::number(std::to_string(walk.disposition)), num(walk.current)}));
    }
    check(fat == before &&
          std::all_of(seen.end() - 9, seen.end(), [](unsigned char c) { return c == 0xa5; }));
    const auto saved = walk;
    const auto bitmap = seen;
    de_fat_walk_step step;
    std::memset(&step, 0xa5, sizeof(step));
    const auto saved_step = step;
    de_view empty{nullptr, 0};
    check(de_fat_walk_feed(&walk, &empty, &step) == DE_INVALID &&
          !std::memcmp(&walk, &saved, sizeof(walk)) &&
          !std::memcmp(&step, &saved_step, sizeof(step)) && seen == bitmap);
    return result.put("steps", std::move(steps))
        .put("pages", std::move(pages))
        .put("count", num(walk.count))
        .put("current", num(walk.current))
        .put("disposition", V::number(std::to_string(walk.disposition)));
}
static int guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    auto *p = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, info.dwPageSize * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    check(p != nullptr);
    auto *boundary = p + info.dwPageSize;
    boundary[-4] = 0xff;
    boundary[-3] = 0xff;
    boundary[-2] = 0xff;
    boundary[-1] = 0xaf;
    DWORD prior = 0;
    check(VirtualProtect(p, info.dwPageSize, PAGE_READONLY, &prior) != 0);
    check(VirtualProtect(boundary, info.dwPageSize, PAGE_NOACCESS, &prior) != 0);
    std::vector<unsigned char> bitmap(8192, 0xa5);
    de_fat_walk walk;
    std::memset(&walk, 0xa5, sizeof(walk));
    const auto saved = walk;
    for (int bits : {0, 12, 16, 32}) {
        const de_u32 bad_count = bits == 12 ? 4085 : bits == 16 ? 65525 : 1;
        check(de_fat_walk_init(bits, bad_count, 2, boundary, 1, &walk) == DE_INVALID &&
              !std::memcmp(&saved, &walk, sizeof(walk)));
    }
    check(de_fat_walk_init(12, 4084, 0, nullptr, 0, &walk) == DE_OK && !walk.running &&
          !walk.count && walk.disposition == DE_FAT_CHAIN_EMPTY);
    check(de_fat_walk_init(12, 4084, 1, nullptr, 0, &walk) == DE_OK && !walk.running &&
          !walk.count && walk.disposition == DE_FAT_CHAIN_INVALID_START);
    walk = saved;
    check(de_fat_walk_init(32, 65525, 2, boundary, 1, &walk) == DE_BUFFER &&
          !std::memcmp(&saved, &walk, sizeof(walk)));
    check(de_fat_walk_init(32, 65525, 2, nullptr, bitmap.size(), &walk) == DE_INVALID &&
          !std::memcmp(&saved, &walk, sizeof(walk)));
    for (std::size_t size = 0; size <= 4; ++size) {
        check(!de_fat_walk_init(32, 65525, 2, bitmap.data(), bitmap.size(), &walk));
        check(bitmap.back() == 0xa5);
        de_view cell{boundary - size, size};
        de_fat_walk_step step{};
        check(!de_fat_walk_feed(&walk, &cell, &step) && !walk.running && walk.count == 1);
        check(walk.disposition == (size == 4 ? DE_FAT_CHAIN_END : DE_FAT_CHAIN_TRUNCATED));
        if (size == 4)
            check(step.entry.raw_value == 0xafffffffUL && step.entry.value == 0x0fffffffUL);
    }
    check(!de_fat_walk_init(32, 65525, 2, bitmap.data(), bitmap.size(), &walk));
    const auto saved_valid = walk;
    const auto saved_bitmap = bitmap;
    de_fat_walk_step step;
    std::memset(&step, 0xa5, sizeof(step));
    const auto saved_step = step;
    de_view overlong{boundary, 5};
    check(de_fat_walk_feed(&walk, &overlong, &step) == DE_BOUNDS &&
          !std::memcmp(&walk, &saved_valid, sizeof(walk)) &&
          !std::memcmp(&step, &saved_step, sizeof(step)) && bitmap == saved_bitmap);
    de_view invalid{nullptr, 1};
    check(de_fat_walk_feed(&walk, &invalid, &step) == DE_INVALID &&
          !std::memcmp(&walk, &saved_valid, sizeof(walk)) &&
          !std::memcmp(&step, &saved_step, sizeof(step)) && bitmap == saved_bitmap);
    check(VirtualFree(p, 0, MEM_RELEASE) != 0);
    std::cout << "Protected exact cells, unchanged error state, capacity-before-access and "
                 "workspace tail passed.\n";
    return 0;
}
int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--guard")
            return guard();
        check(argc == 1);
        disked::json::Limits limits;
        limits.bytes = 8388608;
        limits.string_bytes = 2097152;
        limits.values = 600000;
        std::string line;
        while (std::getline(std::cin, line))
            std::cout << disked::json::dump(observe(disked::json::parse(line, limits)), limits)
                      << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
