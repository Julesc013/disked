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
        throw std::runtime_error("exFAT bitmap invariant");
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
    char p[21];
    need(!de_u64_format(&n, p, sizeof(p)));
    return V::string(p);
}
static std::vector<unsigned char> unhex(const V &v) {
    need(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 16386);
    std::vector<unsigned char> out(v.text.size() / 2);
    for (std::size_t i = 0; i < v.text.size(); ++i) {
        const auto c = v.text[i];
        const auto d = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : 99;
        need(d < 16);
        out[i / 2] = static_cast<unsigned char>((out[i / 2] << 4) | d);
    }
    return out;
}
static V observe(const V &row) {
    auto bytes = unhex(field(row, "bytes"));
    const auto before = bytes;
    de_view view{bytes.data(), bytes.size()};
    auto out = V::object();
    if (field(row, "op").text == "descriptor") {
        de_exfat_bitmap v;
        std::memset(&v, 0xa5, sizeof(v));
        unsigned char saved[sizeof(v)];
        std::memcpy(saved, &v, sizeof(v));
        auto code = de_exfat_bitmap_read(&view, small(field(row, "clusters")),
                                         small(field(row, "shift")), small(field(row, "fats")), &v);
        out.put("status", number(code));
        if (code)
            need(!std::memcmp(saved, &v, sizeof(v)));
        else {
            need(v.raw.data == view.data && v.raw.size == view.size);
            out.put("issues", number(v.issues))
                .put("identifier", number(v.identifier))
                .put("first_cluster", number(v.first_cluster))
                .put("data_length", decimal(v.data_length))
                .put("minimum_bytes", decimal(v.minimum_bytes))
                .put("heap_bytes", decimal(v.heap_bytes))
                .put("valid", V::boolean_value(v.valid != 0));
        }
    } else {
        need(field(row, "op").text == "interval");
        auto offset = exact(field(row, "offset")), length = exact(field(row, "length"));
        de_exfat_bitmap_interval v;
        std::memset(&v, 0xa5, sizeof(v));
        unsigned char saved[sizeof(v)];
        std::memcpy(saved, &v, sizeof(v));
        auto code = de_exfat_bitmap_count(&view, &offset, &length, small(field(row, "clusters")),
                                          small(field(row, "first")), small(field(row, "count")),
                                          small(field(row, "budget")), &v);
        out.put("status", number(code));
        if (code)
            need(!std::memcmp(saved, &v, sizeof(v)));
        else
            out.put("first_cluster", number(v.first_cluster))
                .put("cluster_count", number(v.cluster_count))
                .put("available", number(v.available))
                .put("unavailable", number(v.unavailable))
                .put("first_byte", decimal(v.first_byte))
                .put("last_byte", decimal(v.last_byte));
    }
    need(bytes == before);
    return out;
}
static int guard() {
    auto *memory = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, 16384, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    need(memory != nullptr);
    auto *end = memory + 8192;
    DWORD old = 0;
    need(VirtualProtect(end, 4096, PAGE_NOACCESS, &old) != 0);
    de_exfat_bitmap descriptor{};
    de_exfat_bitmap_interval interval{};
    unsigned char saved[sizeof(interval)];
    std::memcpy(saved, &interval, sizeof(interval));
    auto zero = de_u64_from_u32(0), length = de_u64_from_u32(8192);
    de_view over{end, 8193}, empty{nullptr, 0}, invalid{nullptr, 1};
    need(de_exfat_bitmap_count(&over, &zero, &length, 65536, 2, 1, 1, &interval) == DE_BOUNDS);
    need(de_exfat_bitmap_count(&invalid, &zero, &length, 65536, 2, 1, 1, &interval) == DE_INVALID);
    need(de_exfat_bitmap_count(nullptr, &zero, &length, 65536, 2, 1, 1, &interval) == DE_INVALID);
    need(de_exfat_bitmap_count(&empty, nullptr, &length, 65536, 2, 1, 1, &interval) == DE_INVALID);
    need(!std::memcmp(saved, &interval, sizeof(interval)));
    for (std::size_t n = 0; n <= 32; ++n) {
        auto *start = end - n;
        std::memset(start, 0xff, n);
        de_view view{start, n};
        need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
        auto code = de_exfat_bitmap_read(&view, 10, 9, 1, &descriptor);
        need(code == (n == 32 ? DE_OK : DE_BOUNDS));
        std::memcpy(saved, &interval, sizeof(interval));
        code =
            de_exfat_bitmap_count(&view, &zero, &length, 65536, 2, static_cast<de_u32>(n * 8 + 1),
                                  static_cast<de_u32>(n * 8 + 1), &interval);
        need(code == DE_BOUNDS && !std::memcmp(saved, &interval, sizeof(interval)));
        if (n) {
            need(!de_exfat_bitmap_count(&view, &zero, &length, 65536, 2, static_cast<de_u32>(n * 8),
                                        static_cast<de_u32>(n * 8), &interval));
            need(interval.unavailable == n * 8);
        }
        need(VirtualProtect(memory, 8192, PAGE_READWRITE, &old) != 0);
    }
    std::memset(memory, 0, 8192);
    de_view full{memory, 8192};
    need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
    need(!de_exfat_bitmap_count(&full, &zero, &length, 65536, 2, 65536, 65536, &interval));
    need(interval.available == 65536);
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
        limits.values = 200000;
        limits.string_bytes = 20000;
        auto rows = disked::json::parse(bytes, limits);
        auto out = V::array();
        for (const auto &row : rows.items)
            out.items.push_back(observe(row));
        std::cout << disked::json::dump(out, limits) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 20;
    }
}
