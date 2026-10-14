#include "runtime/capture/exfat_capture.h"
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <deque>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>

using V = disked::json::Value;
static void require(bool value) {
    if (!value)
        throw std::runtime_error("exfat_capture_probe_input");
}
static const V &field(const V &value, const char *key) {
    const auto *result = value.find(key);
    require(result != nullptr);
    return *result;
}
static std::uint64_t integer(const V &value) {
    require(value.kind == V::Kind::string && disked::json::decimal_u64(value.text));
    return std::stoull(value.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static std::uint64_t native(const de_u64 &value) {
    char text[21];
    require(!de_u64_format(&value, text, sizeof(text)));
    return std::stoull(text);
}
static unsigned digit(char c) {
    if (c >= '0' && c <= '9')
        return static_cast<unsigned>(c - '0');
    if (c >= 'a' && c <= 'f')
        return static_cast<unsigned>(c - 'a' + 10);
    throw std::invalid_argument("hex");
}
static std::vector<unsigned char> unhex(const V &value) {
    require(value.kind == V::Kind::string && value.text.size() % 2 == 0);
    std::vector<unsigned char> out(value.text.size() / 2);
    for (std::size_t n = 0; n < out.size(); ++n)
        out[n] = static_cast<unsigned char>(digit(value.text[n * 2]) * 16 +
                                            digit(value.text[n * 2 + 1]));
    return out;
}
struct Region {
    std::uint64_t offset;
    std::vector<unsigned char> bytes;
};
struct ProtectedView {
    unsigned char *allocation = nullptr;
    const unsigned char *data = nullptr;
    explicit ProtectedView(const std::vector<unsigned char> &bytes) {
        require(!bytes.empty() && bytes.size() <= 49153);
        allocation = static_cast<unsigned char *>(
            VirtualAlloc(nullptr, 65536, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
        require(allocation != nullptr);
        auto *begin = allocation + 61440 - bytes.size();
        std::copy(bytes.begin(), bytes.end(), begin);
        DWORD previous = 0;
        require(VirtualProtect(allocation + 61440, 4096, PAGE_NOACCESS, &previous) != 0);
        require(VirtualProtect(allocation, 61440, PAGE_READONLY, &previous) != 0);
        data = begin;
    }
    ~ProtectedView() {
        if (allocation)
            VirtualFree(allocation, 0, MEM_RELEASE);
    }
    ProtectedView(const ProtectedView &) = delete;
    ProtectedView &operator=(const ProtectedView &) = delete;
};
static V observe(const V &input) {
    disked::ExfatCaptureRequest request;
    request.source_id = "generated-exfat";
    if (const auto *v = input.find("source_id")) {
        require(v->kind == V::Kind::string);
        request.source_id = v->text;
    }
    request.epoch = integer(field(input, "epoch"));
    request.source_bytes = integer(field(input, "source_bytes"));
    request.volume_offset = integer(field(input, "offset"));
    request.volume_bytes = integer(field(input, "length"));
    if (const auto *format = input.find("upcase_format")) {
        require(!input.find("compressed") && format->kind == V::Kind::string);
        request.upcase_format =
            format->text == "auto"         ? disked::ExfatUpcaseFormat::Automatic
            : format->text == "compressed" ? disked::ExfatUpcaseFormat::Compressed
            : format->text == "literal"    ? disked::ExfatUpcaseFormat::Literal
                                           : static_cast<disked::ExfatUpcaseFormat>(99);
    } else {
        require(field(input, "compressed").kind == V::Kind::boolean);
        request.upcase_format = field(input, "compressed").boolean
                                    ? disked::ExfatUpcaseFormat::Compressed
                                    : disked::ExfatUpcaseFormat::Literal;
    }
    if (const auto *limits = input.find("limits")) {
        require(limits->kind == V::Kind::object);
#define LOAD_LIMIT(name)                                                                           \
    if (const auto *v = limits->find(#name))                                                       \
    request.limits.name = static_cast<std::size_t>(integer(*v))
        LOAD_LIMIT(read_requests);
        LOAD_LIMIT(read_bytes);
        LOAD_LIMIT(clusters);
        LOAD_LIMIT(records);
        LOAD_LIMIT(retained_bytes);
        LOAD_LIMIT(output_bytes);
#undef LOAD_LIMIT
    }
    std::vector<Region> regions;
    const auto &supplied = field(input, "regions");
    require(supplied.kind == V::Kind::array && supplied.items.size() <= 8192);
    for (const auto &region : supplied.items)
        regions.push_back(Region{integer(field(region, "offset")), unhex(field(region, "hex"))});
    const auto original = regions;
    auto requests = V::array();
    std::deque<std::vector<unsigned char>> buffers;
    std::vector<std::unique_ptr<ProtectedView>> pages;
    const auto *guard = input.find("guard");
    const bool protected_views = guard && guard->boolean;
    const auto *fault = input.find("fault");
    const std::string mode = fault ? field(*fault, "mode").text : "";
    const auto fault_call = fault ? integer(field(*fault, "call")) : 0;
    disked::RegionReader reader = [&](const de_byte_extent &extent) {
        const auto start = native(extent.start), end = native(extent.end);
        require(extent.space &&
                std::string(extent.space->name, extent.space->name_length) == request.source_id);
        require(start >= request.volume_offset && end >= start && end <= request.source_bytes);
        require(end - start <= 49152);
        requests.items.push_back(
            V::object().put("offset", exact(start)).put("bytes", exact(end - start)));
        if (requests.items.size() == fault_call && mode == "throw")
            throw std::runtime_error("generated_reader_failure");
        buffers.emplace_back(static_cast<std::size_t>(end - start), static_cast<unsigned char>(0));
        auto &buffer = buffers.back();
        for (const auto &region : regions) {
            require(region.offset <= UINT64_MAX - region.bytes.size());
            const auto begin = std::max(start, region.offset);
            const auto last = std::min(end, region.offset + region.bytes.size());
            if (begin < last)
                std::copy(region.bytes.begin() + static_cast<std::size_t>(begin - region.offset),
                          region.bytes.begin() + static_cast<std::size_t>(last - region.offset),
                          buffer.begin() + static_cast<std::size_t>(begin - start));
        }
        if (requests.items.size() == fault_call) {
            if (mode == "change")
                buffer[0] ^= 1;
            else if (mode == "short")
                buffer.pop_back();
            else if (mode == "oversized")
                buffer.push_back(0);
            else if (mode == "null")
                return de_view{nullptr, buffer.size()};
        }
        if (protected_views && !buffer.empty()) {
            pages.emplace_back(new ProtectedView(buffer));
            return de_view{pages.back()->data, buffer.size()};
        }
        return de_view{buffer.data(), buffer.size()};
    };
    auto out = V::object();
    try {
        if (mode == "no_reader")
            reader = disked::RegionReader{};
        out.put("observation", disked::observe_exfat_volume(request, reader));
    } catch (const std::invalid_argument &e) {
        out.put("refusal", V::string(e.what()));
    }
    require(regions.size() == original.size());
    for (std::size_t n = 0; n < regions.size(); ++n)
        require(regions[n].offset == original[n].offset && regions[n].bytes == original[n].bytes);
    out.put("protected_views", exact(pages.size()));
    out.put("requests", std::move(requests)).put("source_unchanged", V::boolean_value(true));
    return out;
}
int main() {
    try {
        disked::json::Limits limits;
        limits.bytes = 16777216;
        limits.string_bytes = 12582912;
        limits.values = 524288;
        limits.depth = 32;
        const std::string text((std::istreambuf_iterator<char>(std::cin)),
                               std::istreambuf_iterator<char>());
        const auto input = disked::json::parse(text, limits);
        require(input.kind == V::Kind::array && input.items.size() <= 64);
        auto output = V::array();
        for (const auto &row : input.items)
            output.items.push_back(observe(row));
        std::cout << disked::json::dump(output, limits);
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what();
        return 1;
    }
}
