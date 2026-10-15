#ifndef DISKED_NTFS_PROBE_SUPPORT_H
#define DISKED_NTFS_PROBE_SUPPORT_H
#include "portable/ntfs/ntfs.h"
#include "runtime/command/json.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
inline void need(bool v) {
    if (!v)
        throw std::runtime_error("ntfs_probe_input");
}
inline const V &get(const V &v, const char *key) {
    const auto p = v.find(key);
    need(p != nullptr);
    return *p;
}
inline unsigned small(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    const auto n = std::stoull(v.text);
    need(n <= 65535);
    return static_cast<unsigned>(n);
}
inline V number(de_u32 n) {
    return V::number(std::to_string(n));
}
inline V decimal(const de_u64 &n) {
    char text[21];
    need(!de_u64_format(&n, text, sizeof(text)));
    return V::string(text);
}
inline std::vector<unsigned char> unhex(const V &v) {
    need(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 98306);
    std::vector<unsigned char> b(v.text.size() / 2);
    for (std::size_t i = 0; i < v.text.size(); ++i) {
        const char c = v.text[i];
        const unsigned n = c >= '0' && c <= '9'   ? c - '0'
                           : c >= 'a' && c <= 'f' ? c - 'a' + 10
                                                  : 99;
        need(n < 16);
        b[i / 2] = static_cast<unsigned char>((i % 2 ? b[i / 2] << 4 : 0) | n);
    }
    return b;
}
inline std::string hex(const unsigned char *p, std::size_t n) {
    const char digits[] = "0123456789abcdef";
    std::string text;
    text.reserve(n * 2);
    for (std::size_t i = 0; i < n; ++i) {
        text += digits[p[i] >> 4];
        text += digits[p[i] & 15];
    }
    return text;
}
struct Guard {
    unsigned char *base = nullptr;
    unsigned char *data = nullptr;
    std::size_t bytes = 0;
    explicit Guard(const std::vector<unsigned char> &raw) {
        SYSTEM_INFO info{};
        GetSystemInfo(&info);
        const auto page = static_cast<std::size_t>(info.dwPageSize);
        bytes = ((raw.size() + page - 1) / page + 1) * page;
        base = static_cast<unsigned char *>(
            VirtualAlloc(nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
        need(base != nullptr);
        data = base + bytes - page - raw.size();
        if (!raw.empty())
            std::memcpy(data, raw.data(), raw.size());
        DWORD old = 0;
        need(VirtualProtect(base + bytes - page, page, PAGE_NOACCESS, &old) != FALSE);
        if (bytes > page)
            need(VirtualProtect(base, bytes - page, PAGE_READONLY, &old) != FALSE);
    }
    ~Guard() {
        if (base)
            VirtualFree(base, 0, MEM_RELEASE);
    }
};

inline void process_rows(V (*function)(const V &)) {
    std::string input;
    char block[4096];
    for (;;) {
        const auto n = std::fread(block, 1, sizeof(block), stdin);
        input.append(block, n);
        need(input.size() <= 8388608);
        if (n < sizeof(block))
            break;
    }
    auto limits = disked::json::Limits{};
    limits.bytes = 8388608;
    limits.string_bytes = 2097152;
    limits.values = 262144;
    const auto rows = disked::json::parse(input, limits);
    need(rows.kind == V::Kind::array);
    auto result = V::array();
    for (const auto &row : rows.items)
        result.items.push_back(function(row));
    std::cout << disked::json::dump(result, limits) << '\n';
}
#endif
