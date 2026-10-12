#include "runtime/capture/fat_capture.h"
#include "providers/image/fat_file.h"
#include "portable/fat/fat.h"
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using V = disked::json::Value;
static void require(bool v) {
    if (!v)
        throw std::runtime_error("FAT capture probe invariant");
}
static const V &field(const V &v, const char *key) {
    const auto *x = v.find(key);
    require(x != nullptr);
    return *x;
}
static std::uint64_t integer(const V &v) {
    require(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static std::uint64_t native(const de_u64 &n) {
    char s[21];
    require(!de_u64_format(&n, s, sizeof(s)));
    return std::stoull(s);
}
static unsigned digit(char c) {
    if (c >= '0' && c <= '9')
        return static_cast<unsigned>(c - '0');
    if (c >= 'a' && c <= 'f')
        return static_cast<unsigned>(c - 'a' + 10);
    throw std::runtime_error("hex");
}
static std::vector<unsigned char> unhex(const V &v) {
    require(v.kind == V::Kind::string && v.text.size() % 2 == 0 && v.text.size() <= 8388608);
    std::vector<unsigned char> out(v.text.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i)
        out[i] = static_cast<unsigned char>(digit(v.text[i * 2]) * 16 + digit(v.text[i * 2 + 1]));
    return out;
}
static disked::FatCaptureLimits limits(const V &input) {
    disked::FatCaptureLimits out;
    const auto *supplied = input.find("limits");
    if (!supplied)
        return out;
    require(supplied->kind == V::Kind::object);
#define LOAD_LIMIT(name)                                                                           \
    if (const auto *v = supplied->find(#name))                                                     \
    out.name = static_cast<std::size_t>(integer(*v))
    LOAD_LIMIT(nodes);
    LOAD_LIMIT(depth);
    LOAD_LIMIT(chain_clusters);
    LOAD_LIMIT(total_clusters);
    LOAD_LIMIT(records);
    LOAD_LIMIT(read_requests);
    LOAD_LIMIT(read_bytes);
    LOAD_LIMIT(orphan_groups);
    LOAD_LIMIT(output_bytes);
    LOAD_LIMIT(compare_copies);
    LOAD_LIMIT(allocation_clusters);
    LOAD_LIMIT(allocation_findings);
#undef LOAD_LIMIT
    return out;
}
static V observe(const V &input) {
    const auto &op = field(input, "op");
    require(op.kind == V::Kind::string);
    if (op.text == "cell") {
        const auto bits = integer(field(input, "bits")),
                   clusters = integer(field(input, "clusters")),
                   index = integer(field(input, "index"));
        require(bits <= 64 && clusters <= 0xffffffff && index <= 0xffffffff);
        de_fat_cell_request request{};
        const auto status =
            de_fat_entry_request(static_cast<int>(bits), static_cast<de_u32>(clusters),
                                 static_cast<de_u32>(index), &request);
        auto result = V::object().put("status", exact(static_cast<std::uint64_t>(status)));
        if (!status) {
            result.put("offset", exact(native(request.offset))).put("bytes", exact(request.bytes));
            auto bytes = unhex(field(input, "cell"));
            const auto before = bytes;
            de_view view{bytes.data(), bytes.size()};
            de_fat_entry entry;
            std::memset(&entry, 0xa5, sizeof(entry));
            unsigned char saved[sizeof(entry)];
            std::memcpy(saved, &entry, sizeof(entry));
            const auto decoded =
                de_fat_cell_read(&view, static_cast<int>(bits), static_cast<de_u32>(clusters),
                                 static_cast<de_u32>(index), &entry);
            result.put("cell_status", exact(static_cast<std::uint64_t>(decoded)));
            if (decoded)
                require(!std::memcmp(saved, &entry, sizeof(entry)));
            else
                result.put("raw", exact(entry.raw_value))
                    .put("value", exact(entry.value))
                    .put("kind", exact(static_cast<std::uint64_t>(entry.kind)));
            require(bytes == before);
        }
        return result;
    }
    if (op.text == "file") {
        try {
            const auto *scan = input.find("allocation_scan");
            require(!scan || scan->kind == V::Kind::boolean);
            return V::object().put(
                "result",
                disked::capture_fat_file(field(input, "path").text, integer(field(input, "offset")),
                                         integer(field(input, "length")),
                                         static_cast<std::uint32_t>(integer(field(input, "copy"))),
                                         limits(input), scan && scan->boolean));
        } catch (const std::exception &error) {
            return V::object().put("error", V::string(error.what()));
        }
    }
    require(op.text == "observe");
    disked::FatCaptureRequest request;
    request.source_id =
        input.find("source_id") ? input.find("source_id")->text : "generated-fat-source";
    request.epoch = input.find("epoch") ? integer(*input.find("epoch")) : 1;
    request.source_bytes = integer(field(input, "source_bytes"));
    request.volume_offset = integer(field(input, "offset"));
    request.volume_bytes = integer(field(input, "length"));
    const auto copy = integer(field(input, "copy"));
    require(copy <= 0xffffffff);
    request.fat_copy = static_cast<std::uint32_t>(copy);
    request.limits = limits(input);
    if (const auto *scan = input.find("allocation_scan")) {
        require(scan->kind == V::Kind::boolean);
        request.allocation_scan = scan->boolean;
    }
    struct Segment {
        std::uint64_t start;
        std::vector<unsigned char> bytes;
    };
    std::vector<Segment> segments;
    const auto &values = field(input, "regions");
    require(values.kind == V::Kind::array && values.items.size() <= 1024);
    std::size_t total = 0;
    for (const auto &row : values.items) {
        Segment s{integer(field(row, "offset")), unhex(field(row, "hex"))};
        total += s.bytes.size();
        require(total <= 4194304 && s.start <= request.source_bytes &&
                s.bytes.size() <= request.source_bytes - s.start);
        segments.push_back(std::move(s));
    }
    const auto saved_segments = segments;
    std::deque<std::vector<unsigned char>> captured;
    auto calls = V::array();
    auto read = [&](const de_byte_extent &extent) {
        const auto start = native(extent.start), end = native(extent.end);
        require(end >= start && end - start <= 4096);
        calls.items.push_back(
            V::object().put("offset", exact(start)).put("bytes", exact(end - start)));
        std::vector<unsigned char> bytes(static_cast<std::size_t>(end - start), 0);
        for (const auto &s : segments) {
            const auto first = std::max(start, s.start),
                       last = std::min(end, s.start + s.bytes.size());
            if (first < last)
                std::copy(s.bytes.begin() + static_cast<std::size_t>(first - s.start),
                          s.bytes.begin() + static_cast<std::size_t>(last - s.start),
                          bytes.begin() + static_cast<std::size_t>(first - start));
        }
        if (const auto *fault = input.find("fault")) {
            const auto at = integer(field(*fault, "call"));
            if (calls.items.size() == at) {
                const auto mode = field(*fault, "kind").text;
                if (mode == "throw")
                    throw std::runtime_error("injected_reader_error");
                if (mode == "short" && !bytes.empty())
                    bytes.pop_back();
                if (mode == "oversized")
                    bytes.push_back(0);
                if (mode == "change" && !bytes.empty())
                    bytes[0] ^= 1;
                if (mode == "null") {
                    captured.push_back(std::move(bytes));
                    return de_view{nullptr, captured.back().size()};
                }
            }
        }
        captured.push_back(std::move(bytes));
        const auto &out = captured.back();
        return de_view{out.data(), out.size()};
    };
    auto output = V::object();
    try {
        output.put("report", disked::observe_fat_volume(request, read));
    } catch (const std::exception &error) {
        output.put("error", V::string(error.what()));
    }
    for (std::size_t i = 0; i < segments.size(); ++i)
        require(segments[i].start == saved_segments[i].start &&
                segments[i].bytes == saved_segments[i].bytes);
    output.put("calls", std::move(calls)).put("inputs_unchanged", V::boolean_value(true));
    return output;
}
static int guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    auto *pages = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, info.dwPageSize * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    require(pages != nullptr);
    auto *end = pages + info.dwPageSize;
    end[-1] = 0xff;
    end[-2] = 0xf0;
    DWORD old = 0;
    require(VirtualProtect(pages, info.dwPageSize, PAGE_READONLY, &old) != 0 &&
            VirtualProtect(end, info.dwPageSize, PAGE_NOACCESS, &old) != 0);
    de_view view{end - 2, 2};
    de_fat_entry value{};
    require(!de_fat_cell_read(&view, 12, 2847, 341, &value) && value.value == 0xfff);
    for (auto n : {0U, 1U, 3U, 4U}) {
        de_view wrong{end, n};
        unsigned char saved[sizeof(value)];
        std::memcpy(saved, &value, sizeof(value));
        require(de_fat_cell_read(&wrong, 12, 2847, 341, &value) == DE_BOUNDS &&
                !std::memcmp(saved, &value, sizeof(value)));
    }
    require(VirtualFree(pages, 0, MEM_RELEASE) != 0);
    std::puts("FAT stream-cell protected bounds and no resident-table request checks passed.");
    return 0;
}
int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--guard")
            return guard();
        require(argc == 1);
        disked::json::Limits l;
        l.bytes = 16777216;
        l.string_bytes = 8388608;
        l.values = 262144;
        l.depth = 64;
        std::string line;
        while (std::getline(std::cin, line)) {
            require(line.size() <= l.bytes);
            std::cout << disked::json::dump(observe(disked::json::parse(line, l)), l) << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
