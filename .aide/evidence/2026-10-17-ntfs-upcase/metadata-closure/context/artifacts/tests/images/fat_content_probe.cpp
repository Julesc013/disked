#include "runtime/capture/fat_content.h"
#include "runtime/capture/fat_capture.h"
#include <algorithm>
#include <deque>
#include <iostream>

using V = disked::json::Value;
using Bytes = std::vector<unsigned char>;
static void require(bool yes) {
    if (!yes)
        throw std::runtime_error("content fixture invariant");
}
static const V &field(const V &v, const char *key) {
    auto *p = v.find(key);
    require(p != nullptr);
    return *p;
}
static std::uint64_t integer(const V &v) {
    require(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static std::uint64_t native(const de_u64 &n) {
    char text[21];
    require(!de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
static Bytes unhex(const V &v) {
    require(v.kind == V::Kind::string && !(v.text.size() % 2));
    auto digit = [](char c) -> unsigned {
        if (c >= '0' && c <= '9')
            return static_cast<unsigned>(c - '0');
        require(c >= 'a' && c <= 'f');
        return static_cast<unsigned>(c - 'a' + 10);
    };
    Bytes out(v.text.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i)
        out[i] = static_cast<unsigned char>(digit(v.text[i * 2]) * 16 + digit(v.text[i * 2 + 1]));
    return out;
}
static void changes(V &value, const V *items) {
    if (!items)
        return;
    for (const auto &item : items->items) {
        auto *at = &value;
        const auto &path = field(item, "path").items;
        require(!path.empty());
        for (std::size_t i = 0; i + 1 < path.size(); ++i) {
            at = at->kind == V::Kind::array
                     ? &at->items.at(static_cast<std::size_t>(integer(path[i])))
                     : &at->fields.at(path[i].text);
        }
        if (at->kind == V::Kind::array)
            at->items.at(static_cast<std::size_t>(integer(path.back()))) = field(item, "value");
        else
            at->fields.at(path.back().text) = field(item, "value");
    }
}
static V run(const V &input) {
    const auto &source = field(input, "source");
    disked::FatCaptureRequest request;
    request.source_id = "generated-content-source";
    request.epoch = 1;
    request.source_bytes = integer(field(source, "source_bytes"));
    request.volume_offset = integer(field(source, "offset"));
    request.volume_bytes = integer(field(source, "length"));
    request.fat_copy = static_cast<std::uint32_t>(integer(field(source, "copy")));
    struct Region {
        std::uint64_t offset;
        Bytes bytes;
    };
    std::vector<Region> regions;
    for (const auto &row : field(source, "regions").items) {
        regions.push_back({integer(field(row, "offset")), unhex(field(row, "hex"))});
        require(regions.back().offset <= request.source_bytes &&
                regions.back().bytes.size() <= request.source_bytes - regions.back().offset);
    }
    const auto original = disked::json::dump(source, {8388608, 64, 262144, 4194304});
    std::deque<Bytes> buffers;
    auto read = [&](const de_byte_extent &range) -> de_view {
        const auto offset = native(range.start), end = native(range.end);
        require(std::string(range.space->name, range.space->name_length) == request.source_id &&
                offset <= end && end <= request.source_bytes && end - offset <= 4096);
        buffers.emplace_back(static_cast<std::size_t>(end - offset), static_cast<unsigned char>(0));
        auto &bytes = buffers.back();
        for (const auto &region : regions) {
            const auto begin = std::max(offset, region.offset);
            const auto finish = std::min(end, region.offset + region.bytes.size());
            if (begin < finish)
                std::copy(region.bytes.begin() + static_cast<std::size_t>(begin - region.offset),
                          region.bytes.begin() + static_cast<std::size_t>(finish - region.offset),
                          bytes.begin() + static_cast<std::size_t>(begin - offset));
        }
        return {bytes.data(), bytes.size()};
    };
    auto observation = disked::observe_fat_volume(request, read);
    changes(observation, input.find("changes"));
    disked::FatContentBinding binding{request.source_id,    request.epoch,
                                      request.source_bytes, request.volume_offset,
                                      request.volume_bytes, request.fat_copy};
    if (auto *change = input.find("binding")) {
        if (auto *v = change->find("source_id"))
            binding.source_id = v->text;
        if (auto *v = change->find("epoch"))
            binding.epoch = integer(*v);
        if (auto *v = change->find("source_bytes"))
            binding.source_bytes = integer(*v);
        if (auto *v = change->find("volume_offset"))
            binding.volume_offset = integer(*v);
        if (auto *v = change->find("volume_bytes"))
            binding.volume_bytes = integer(*v);
        if (auto *v = change->find("fat_copy"))
            binding.fat_copy = static_cast<std::uint32_t>(integer(*v));
    }
    auto calls = V::array();
    auto result = V::object();
    try {
        auto map = disked::prepare_fat_content(observation, integer(field(input, "node")), binding);
        disked::FatContentLimits limits;
        if (auto *v = input.find("limits")) {
            if (auto *n = v->find("bytes"))
                limits.bytes = static_cast<std::size_t>(integer(*n));
            if (auto *n = v->find("read_requests"))
                limits.read_requests = static_cast<std::size_t>(integer(*n));
            if (auto *n = v->find("read_chunk"))
                limits.read_chunk = static_cast<std::size_t>(integer(*n));
        }
        disked::RegionReader port = [&](const de_byte_extent &range) -> de_view {
            auto view = read(range);
            const auto call = calls.items.size();
            calls.items.push_back(V::object()
                                      .put("offset", exact(native(range.start)))
                                      .put("bytes", exact(view.size)));
            if (auto *fault = input.find("fault")) {
                const auto at = input.find("fault_at") ? integer(*input.find("fault_at")) : 0;
                if (call == at) {
                    if (fault->text == "throw")
                        throw std::runtime_error("untrusted reader diagnostic");
                    if (fault->text == "short")
                        return {view.data, view.size - 1};
                    if (fault->text == "zero")
                        return {};
                    if (fault->text == "null")
                        return {nullptr, view.size};
                    if (fault->text == "long")
                        return {reinterpret_cast<const unsigned char *>(1), view.size + 1};
                }
            }
            return view;
        };
        if (input.find("no_reader"))
            port = {};
        result.put("result", map.read(integer(field(input, "offset")),
                                      static_cast<std::size_t>(integer(field(input, "count"))),
                                      port, limits));
    } catch (const disked::FatContentError &error) {
        result.put("error", V::string(error.code));
    }
    result.put("calls", std::move(calls));
    result.put("observation", std::move(observation));
    result.put(
        "inputs_unchanged",
        V::boolean_value(original == disked::json::dump(source, {8388608, 64, 262144, 4194304})));
    return result;
}
int main() {
    try {
        std::string line;
        disked::json::Limits limits{8388608, 64, 262144, 4194304};
        while (std::getline(std::cin, line))
            std::cout << disked::json::dump(run(disked::json::parse(line, limits)), limits) << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
