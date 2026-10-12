#include "runtime/capture/fat_capture.h"
#include "providers/image/fat_file.h"
#include "portable/fat/fat.h"
#include "platform/windows/file_names.h"
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
static disked::FatAllocationWindow allocation_window(const V &input) {
    disked::FatAllocationWindow out;
    if (const auto *window = input.find("allocation_window")) {
        require(window->kind == V::Kind::object && window->fields.size() == 2);
        const auto first = integer(field(*window, "first_cluster"));
        const auto count = integer(field(*window, "clusters"));
        require(first <= 0xffffffff && count <= 0xffffffff);
        out = {static_cast<std::uint32_t>(first), static_cast<std::uint32_t>(count)};
    }
    return out;
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
static disked::FatNameUnits name_units(const V &v) {
    require(v.kind == V::Kind::array && v.items.size() <= 260);
    disked::FatNameUnits out;
    for (const auto &item : v.items) {
        const auto n = integer(item);
        require(n <= 65535);
        out.push_back(static_cast<std::uint16_t>(n));
    }
    return out;
}
static std::vector<disked::FatNameQuery> name_queries(const V &input) {
    std::vector<disked::FatNameQuery> out;
    if (const auto *v = input.find("namespace_queries")) {
        require(v->kind == V::Kind::array && v->items.size() <= 16);
        for (const auto &q : v->items) {
            const auto id = integer(field(q, "directory"));
            require(id <= 128);
            out.push_back({static_cast<std::size_t>(id), name_units(field(q, "units"))});
        }
    }
    return out;
}
static disked::FatNamespaceLimits name_limits(const V &input) {
    disked::FatNamespaceLimits out;
    if (const auto *v = input.find("namespace_limits")) {
        require(v->kind == V::Kind::object);
        if (const auto *n = v->find("comparisons"))
            out.comparisons = static_cast<std::size_t>(integer(*n));
        if (const auto *n = v->find("findings"))
            out.findings = static_cast<std::size_t>(integer(*n));
        if (const auto *n = v->find("output_bytes"))
            out.output_bytes = static_cast<std::size_t>(integer(*n));
    }
    return out;
}
static disked::FatNameConsumer name_consumer(const V &input) {
    const auto page = integer(field(input, "namespace_code_page"));
    require(page <= 0xffffffff);
    auto out = disked::windows_fat_name_consumer(static_cast<std::uint32_t>(page));
    // Fault callbacks exist only in this test executable, never in the platform adapter.
    if (const auto *fault = input.find("consumer_fault")) {
        const auto mode = fault->text;
        const auto original = out.equal;
        if (mode == "equal_unknown" || mode == "equal_throw" || mode == "equal_invalid" ||
            mode == "nonreflexive" || mode == "asymmetric")
            out.equal = [mode, original](const disked::FatNameUnits &a,
                                         const disked::FatNameUnits &b) {
                if (mode == "equal_throw")
                    throw std::runtime_error("test_comparison_exception");
                if (mode == "equal_invalid")
                    return static_cast<disked::FatNameEquality>(99);
                if (mode == "equal_unknown")
                    return disked::FatNameEquality::Unknown;
                if (mode == "nonreflexive")
                    return disked::FatNameEquality::Different;
                if (a != b)
                    return a < b ? disked::FatNameEquality::Equal
                                 : disked::FatNameEquality::Different;
                return original(a, b);
            };
        else if (mode == "decode_unknown" || mode == "decode_throw" || mode == "decode_invalid")
            out.decode_short =
                [mode](const std::array<unsigned char, 11> &) -> disked::FatNameDecode {
                if (mode == "decode_throw")
                    throw std::runtime_error("test_decode_exception");
                disked::FatNameDecode d;
                if (mode == "decode_invalid")
                    d.assessment.state = static_cast<disked::FatNameState>(99);
                return d;
            };
        else if (mode == "component_unknown" || mode == "component_throw" ||
                 mode == "component_invalid")
            out.component = [mode](const disked::FatNameUnits &) -> disked::FatNameAssessment {
                if (mode == "component_throw")
                    throw std::runtime_error("test_component_exception");
                return {mode == "component_invalid" ? static_cast<disked::FatNameState>(99)
                                                    : disked::FatNameState::Unknown,
                        "test_unknown"};
            };
        else if (mode == "missing_callback")
            out.equal = {};
        else if (mode == "invalid_identity")
            out.id.clear();
        else if (mode == "invalid_binding")
            out.binding = V::array();
        else
            require(false);
    }
    return out;
}
static V namespace_observe(const V &input) {
    auto consumer = name_consumer(input);
    std::vector<disked::FatNamespaceDirectory> directories;
    std::vector<disked::FatNamespaceEntry> entries;
    for (const auto &d : field(input, "directories").items) {
        const auto id = integer(field(d, "id"));
        require(id <= 128);
        directories.push_back({static_cast<std::size_t>(id), field(d, "complete").boolean});
    }
    for (const auto &e : field(input, "entries").items) {
        disked::FatNamespaceEntry entry;
        const auto id = integer(field(e, "id")), parent = integer(field(e, "parent"));
        require(id <= 128 && parent <= 128);
        entry.id = static_cast<std::size_t>(id);
        entry.parent = static_cast<std::size_t>(parent);
        const auto stored = unhex(field(e, "short"));
        require(stored.size() == 11);
        std::copy(stored.begin(), stored.end(), entry.short_name.begin());
        entry.source_record_offset =
            input.find("record_offset") ? integer(*input.find("record_offset")) : 4096 + id * 32;
        entry.kind = disked::FatNamespaceKind::File;
        if (const auto *k = e.find("kind")) {
            entry.kind = k->text == "directory"  ? disked::FatNamespaceKind::Directory
                         : k->text == "excluded" ? disked::FatNamespaceKind::Excluded
                         : k->text == "unknown"  ? disked::FatNamespaceKind::Unknown
                                                 : disked::FatNamespaceKind::File;
        }
        if (const auto *n = e.find("long")) {
            entry.has_long_name = true;
            entry.long_name = name_units(*n);
            entry.long_associated = !e.find("associated") || e.find("associated")->boolean;
            entry.long_unicode_valid = !e.find("unicode_valid") || e.find("unicode_valid")->boolean;
            entry.long_canonical = !e.find("canonical") || e.find("canonical")->boolean;
        }
        entries.push_back(std::move(entry));
    }
    return disked::observe_fat_namespace(
        directories, entries, consumer, name_queries(input), name_limits(input),
        !input.find("applicable") || input.find("applicable")->boolean);
}
static V observe(const V &input) {
    const auto &op = field(input, "op");
    require(op.kind == V::Kind::string);
    if (op.text == "namespace") {
        try {
            return V::object().put("namespace", namespace_observe(input));
        } catch (const std::exception &error) {
            return V::object().put("error", V::string(error.what()));
        }
    }
    if (op.text == "header" || op.text == "fsinfo") {
        auto bytes = unhex(field(input, "raw"));
        const auto saved = bytes;
        const bool null_data = input.find("null") && input.find("null")->boolean;
        de_view view{null_data ? nullptr : bytes.data(), bytes.size()};
        auto result = V::object();
        if (op.text == "header") {
            const auto bits = integer(field(input, "bits")), media = integer(field(input, "media"));
            require(bits <= 64 && media <= 255);
            de_fat_header value;
            std::memset(&value, 0xa5, sizeof(value));
            unsigned char before[sizeof(value)];
            std::memcpy(before, &value, sizeof(value));
            const auto status = de_fat_header_read(&view, static_cast<int>(bits),
                                                   static_cast<unsigned char>(media), &value);
            result.put("status", exact(static_cast<std::uint64_t>(status)));
            if (status)
                require(!std::memcmp(before, &value, sizeof(value)));
            else
                result.put("issues", exact(value.issues))
                    .put("raw_zero", exact(value.raw_zero))
                    .put("raw_one", exact(value.raw_one))
                    .put("zero", exact(value.zero))
                    .put("one", exact(value.one))
                    .put("fields_present", V::boolean_value(value.fields_present != 0))
                    .put("flags_supported", V::boolean_value(value.flags_supported != 0))
                    .put("clean_shutdown", V::boolean_value(value.clean_shutdown != 0))
                    .put("no_io_error", V::boolean_value(value.no_io_error != 0));
        } else {
            const auto unit = integer(field(input, "unit")),
                       clusters = integer(field(input, "clusters"));
            require(unit <= 0xffffffff && clusters <= 0xffffffff);
            de_fat_fsinfo value;
            std::memset(&value, 0xa5, sizeof(value));
            unsigned char before[sizeof(value)];
            std::memcpy(before, &value, sizeof(value));
            const auto status = de_fat_fsinfo_read(&view, static_cast<de_u32>(unit),
                                                   static_cast<de_u32>(clusters), &value);
            result.put("status", exact(static_cast<std::uint64_t>(status)));
            if (status)
                require(!std::memcmp(before, &value, sizeof(value)));
            else
                result.put("issues", exact(value.issues))
                    .put("reserved_nonzero", exact(value.reserved_nonzero))
                    .put("free_count", exact(value.free_count))
                    .put("next_free", exact(value.next_free))
                    .put("fields_present", V::boolean_value(value.fields_present != 0))
                    .put("free_count_known", V::boolean_value(value.free_count_known != 0))
                    .put("next_free_known", V::boolean_value(value.next_free_known != 0));
        }
        require(bytes == saved);
        result.put("inputs_unchanged", V::boolean_value(true));
        return result;
    }
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
            const auto *aux = input.find("auxiliary_checks");
            require(!aux || aux->kind == V::Kind::boolean);
            const auto copy = integer(field(input, "copy"));
            require(copy <= 0xffffffff);
            disked::FatNameConsumer consumer;
            const bool names = input.find("namespace_code_page") != nullptr;
            if (names)
                consumer = name_consumer(input);
            return V::object().put(
                "result", disked::capture_fat_file(
                              field(input, "path").text, integer(field(input, "offset")),
                              integer(field(input, "length")), static_cast<std::uint32_t>(copy),
                              limits(input), scan && scan->boolean, aux && aux->boolean,
                              names ? &consumer : nullptr, name_queries(input), name_limits(input),
                              allocation_window(input)));
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
    request.allocation_window = allocation_window(input);
    disked::FatNameConsumer consumer;
    if (input.find("namespace_code_page")) {
        consumer = name_consumer(input);
        request.namespace_consumer = &consumer;
    }
    request.namespace_queries = name_queries(input);
    request.namespace_limits = name_limits(input);
    if (const auto *scan = input.find("allocation_scan")) {
        require(scan->kind == V::Kind::boolean);
        request.allocation_scan = scan->boolean;
    }
    if (const auto *aux = input.find("auxiliary_checks")) {
        require(aux->kind == V::Kind::boolean);
        request.auxiliary_checks = aux->boolean;
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
static int auxiliary_guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    require(info.dwPageSize >= 512);
    auto *pages = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, info.dwPageSize * 2, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    require(pages != nullptr);
    auto *end = pages + info.dwPageSize, *raw = end - 512;
    const unsigned char lead[]{0x52, 0x52, 0x61, 0x41}, structure[]{0x72, 0x72, 0x41, 0x61},
        trail[]{0, 0, 0x55, 0xaa};
    std::memcpy(raw, lead, 4);
    std::memcpy(raw + 484, structure, 4);
    std::memcpy(raw + 508, trail, 4);
    std::fill(raw + 488, raw + 496, static_cast<unsigned char>(0xff));
    DWORD old = 0;
    require(VirtualProtect(pages, info.dwPageSize, PAGE_READONLY, &old) != 0 &&
            VirtualProtect(end, info.dwPageSize, PAGE_NOACCESS, &old) != 0);
    de_view view{raw, 512};
    de_fat_fsinfo fs{};
    require(!de_fat_fsinfo_read(&view, 4096, 65525, &fs) && fs.fields_present &&
            fs.issues == DE_FAT_FSINFO_TRUNCATED && !fs.free_count_known && !fs.next_free_known);
    const auto saved_fs = fs;
    view = {end, 4097};
    require(de_fat_fsinfo_read(&view, 4096, 65525, &fs) == DE_BOUNDS &&
            !std::memcmp(&fs, &saved_fs, sizeof(fs)));
    de_fat_header header{};
    for (auto bits : {12, 16, 32}) {
        const auto count = bits == 12 ? 3U : (bits == 16 ? 4U : 8U);
        view = {end - count, count};
        require(!de_fat_header_read(&view, bits, 0xf8, &header) && header.fields_present);
        const auto saved_header = header;
        view = {end, count + 1};
        require(de_fat_header_read(&view, bits, 0xf8, &header) == DE_BOUNDS &&
                !std::memcmp(&header, &saved_header, sizeof(header)));
    }
    require(VirtualFree(pages, 0, MEM_RELEASE) != 0);
    std::puts("FAT auxiliary protected prefix/header bounds and unchanged error outputs passed.");
    return 0;
}
int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--guard")
            return guard();
        if (argc == 2 && std::string(argv[1]) == "--aux-guard")
            return auxiliary_guard();
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
