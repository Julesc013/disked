#include "portable/exfat/exfat.h"
#include "runtime/command/json.h"
#include "portable/hash/sha256.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
static void need(bool value) {
    if (!value)
        throw std::runtime_error("upcase probe invariant");
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
    char text[21];
    need(!de_u64_format(&n, text, sizeof(text)));
    return V::string(text);
}
static std::vector<unsigned char> unhex(const V &v) {
    need(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 524290);
    std::vector<unsigned char> out(v.text.size() / 2);
    for (std::size_t i = 0; i < v.text.size(); ++i) {
        auto c = v.text[i];
        auto n = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : 99;
        need(n < 16);
        out[i / 2] = static_cast<unsigned char>((out[i / 2] << 4) | n);
    }
    return out;
}
static std::vector<unsigned short> units(const V &v) {
    need(v.kind == V::Kind::array && v.items.size() <= 256);
    std::vector<unsigned short> out;
    for (const auto &x : v.items) {
        auto n = small(x);
        need(n <= 65535);
        out.push_back(static_cast<unsigned short>(n));
    }
    return out;
}
static V observe(const V &row) {
    auto bytes = unhex(field(row, "bytes"));
    const auto before = bytes;
    auto result = V::object();
    if (field(row, "op").text == "descriptor") {
        de_exfat_upcase_descriptor v;
        std::memset(&v, 0xa5, sizeof(v));
        unsigned char saved[sizeof(v)];
        std::memcpy(saved, &v, sizeof(v));
        de_view view{bytes.data(), bytes.size()};
        auto code = de_exfat_upcase_descriptor_read(&view, small(field(row, "clusters")),
                                                    small(field(row, "shift")), &v);
        result.put("status", number(code));
        if (code)
            need(!std::memcmp(saved, &v, sizeof(v)));
        else {
            need(v.raw.data == view.data && v.raw.size == view.size);
            result.put("issues", number(v.issues))
                .put("table_checksum", number(v.table_checksum))
                .put("first_cluster", number(v.first_cluster))
                .put("data_length", decimal(v.data_length))
                .put("heap_bytes", decimal(v.heap_bytes))
                .put("valid", V::boolean_value(v.valid != 0));
        }
    } else {
        need(field(row, "op").text == "stream");
        de_exfat_upcase state;
        std::memset(&state, 0xa5, sizeof(state));
        unsigned char init_saved[sizeof(state)];
        std::memcpy(init_saved, &state, sizeof(state));
        auto code = de_exfat_upcase_init(small(field(row, "length")), small(field(row, "checksum")),
                                         static_cast<int>(small(field(row, "compressed"))), &state);
        result.put("init_status", number(code));
        if (code)
            need(!std::memcmp(init_saved, &state, sizeof(state)));
        else {
            auto statuses = V::array();
            std::vector<unsigned short> map;
            map.reserve(65536);
            std::size_t raw_at = 0;
            const auto validation = small(field(row, "validation")) != 0;
            for (const auto &action : field(row, "actions").items) {
                auto n = small(field(action, "size"));
                need(n <= bytes.size() - raw_at);
                de_view chunk{bytes.data() + raw_at, n};
                auto offset = small(field(action, "offset"));
                auto mappings = small(field(action, "mapping_budget")),
                     capacity = small(field(action, "capacity"));
                need(capacity <= 65536);
                std::vector<unsigned short> output(capacity ? capacity : 1, 0x5a5a);
                const auto saved_output = output;
                const auto saved_state = state;
                de_exfat_upcase_step step;
                std::memset(&step, 0xa5, sizeof(step));
                unsigned char saved_step[sizeof(step)];
                std::memcpy(saved_step, &step, sizeof(step));
                auto status = de_exfat_upcase_feed(
                    &state, &chunk, offset, small(field(action, "byte_budget")), mappings,
                    validation ? nullptr : output.data(), validation ? 0 : capacity, &step);
                statuses.items.push_back(number(status));
                if (status) {
                    need(!std::memcmp(&state, &saved_state, sizeof(state)));
                    need(output == saved_output);
                    need(!std::memcmp(&step, saved_step, sizeof(step)));
                } else {
                    need(step.first_mapping == map.size() || validation);
                    need(step.consumed_bytes == n);
                    if (!validation)
                        map.insert(map.end(), output.begin(),
                                   output.begin() + step.emitted_mappings);
                    raw_at += n;
                }
            }
            const auto before_finish = state;
            auto finish = de_exfat_upcase_finish(&state);
            if (finish)
                need(!std::memcmp(&state, &before_finish, sizeof(state)));
            result.put("statuses", std::move(statuses))
                .put("finish_status", number(finish))
                .put("issues", number(state.issues))
                .put("checksum", number(state.checksum))
                .put("consumed", number(state.consumed))
                .put("mapped", number(state.mapped))
                .put("pending", number(state.pending_identity))
                .put("valid", V::boolean_value(state.valid != 0));
            std::vector<unsigned char> encoded;
            for (auto n : map) {
                encoded.push_back(static_cast<unsigned char>(n));
                encoded.push_back(static_cast<unsigned char>(n >> 8));
            }
            unsigned char digest[32];
            disked::sha256(encoded.data(), encoded.size(), digest);
            static const char digits[] = "0123456789abcdef";
            std::string hash = "sha256:";
            for (auto n : digest) {
                hash += digits[n >> 4];
                hash += digits[n & 15];
            }
            result.put("map_sha256", V::string(hash));
            auto comparisons = V::array();
            for (const auto &pair : field(row, "names").items) {
                auto left = units(field(pair, "left")), right = units(field(pair, "right"));
                unsigned short a = 0x5a5a, b = 0x5a5a;
                int equal = 7;
                auto sa = de_exfat_name_hash(map.data(), map.size(), left.data(), left.size(), &a),
                     sb =
                         de_exfat_name_hash(map.data(), map.size(), right.data(), right.size(), &b),
                     se = de_exfat_name_equal(map.data(), map.size(), left.data(), left.size(),
                                              right.data(), right.size(), &equal);
                if (sa)
                    need(a == 0x5a5a);
                if (sb)
                    need(b == 0x5a5a);
                if (se)
                    need(equal == 7);
                comparisons.items.push_back(V::object()
                                                .put("left_status", number(sa))
                                                .put("right_status", number(sb))
                                                .put("equal_status", number(se))
                                                .put("left_hash", number(a))
                                                .put("right_hash", number(b))
                                                .put("equal", V::number(std::to_string(equal))));
            }
            result.put("names", std::move(comparisons));
        }
    }
    need(bytes == before);
    return result;
}
static int guard() {
    auto *memory = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, 16384, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    need(memory != nullptr);
    auto *end = memory + 8192;
    DWORD old = 0;
    need(VirtualProtect(end, 4096, PAGE_NOACCESS, &old) != 0);
    de_exfat_upcase state{};
    de_exfat_upcase_step step{};
    need(!de_exfat_upcase_init(131072, 0, 0, &state));
    de_view over{end, 8193};
    auto saved = state;
    need(de_exfat_upcase_feed(&state, &over, 0, 8193, 65536, nullptr, 0, &step) == DE_BOUNDS);
    need(!std::memcmp(&state, &saved, sizeof(state)));
    de_view empty{nullptr, 0}, invalid{nullptr, 1};
    need(de_exfat_upcase_feed(nullptr, &empty, 0, 0, 0, nullptr, 0, &step) == DE_INVALID);
    need(de_exfat_upcase_feed(&state, &invalid, 0, 1, 1, nullptr, 0, &step) == DE_INVALID);
    need(de_exfat_upcase_feed(&state, &empty, 0, 0, 0, nullptr, 0, nullptr) == DE_INVALID);
    need(de_exfat_upcase_finish(&state) == DE_INVALID);
    need(!std::memcmp(&state, &saved, sizeof(state)));
    for (auto n : {std::size_t(0), std::size_t(1), std::size_t(2), std::size_t(3), std::size_t(4),
                   std::size_t(4095), std::size_t(4096), std::size_t(8191), std::size_t(8192)}) {
        auto *start = end - n;
        std::memset(start, 0, n);
        de_view chunk{start, n};
        need(!de_exfat_upcase_init(131072, 0, 0, &state));
        need(VirtualProtect(memory, 8192, PAGE_READONLY, &old) != 0);
        need(!de_exfat_upcase_feed(&state, &chunk, 0, static_cast<de_u32>(n), 65536, nullptr, 0,
                                   &step));
        need(VirtualProtect(memory, 8192, PAGE_READWRITE, &old) != 0);
    }
    auto *outmemory = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, 8192, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    need(outmemory != nullptr);
    need(VirtualProtect(outmemory + 4096, 4096, PAGE_NOACCESS, &old) != 0);
    auto *output = reinterpret_cast<unsigned short *>(outmemory + 4096) - 1;
    unsigned char raw[2] = {0, 0};
    de_view two{raw, 2};
    need(!de_exfat_upcase_init(131072, 0, 0, &state));
    saved = state;
    *output = 0x5a5a;
    need(de_exfat_upcase_feed(&state, &two, 0, 2, 1, output, 0, &step) == DE_BUFFER);
    need(*output == 0x5a5a && !std::memcmp(&state, &saved, sizeof(state)));
    need(!de_exfat_upcase_feed(&state, &two, 0, 2, 1, output, 1, &step));
    need(*output == 0);
    de_exfat_upcase_descriptor descriptor{};
    for (std::size_t n = 0; n < 32; ++n) {
        de_view view{end - n, n};
        need(de_exfat_upcase_descriptor_read(&view, 4096, 9, &descriptor) == DE_BOUNDS);
    }
    need(VirtualFree(memory, 0, MEM_RELEASE) != 0);
    need(VirtualFree(outmemory, 0, MEM_RELEASE) != 0);
    std::cout << "guard passed\n";
    return 0;
}
int main(int argc, char **argv) {
    try {
        if (argc == 2 && !std::strcmp(argv[1], "--guard"))
            return guard();
        std::string bytes((std::istreambuf_iterator<char>(std::cin)), {});
        disked::json::Limits limits;
        limits.bytes = 32 * 1024 * 1024;
        limits.values = 1000000;
        limits.string_bytes = 524300;
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
