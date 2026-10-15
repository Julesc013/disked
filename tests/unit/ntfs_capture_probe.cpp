#include "runtime/capture/ntfs_capture.h"
#include "ntfs_probe_support.h"
#include <algorithm>
#include <memory>

using disked::NtfsCaptureRequest;
static std::uint64_t integer(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static std::uint64_t native(const de_u64 &value) {
    return integer(decimal(value));
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
struct Region {
    std::uint64_t start;
    std::vector<unsigned char> bytes;
};
static V observe(const V &input) {
    NtfsCaptureRequest request;
    request.source_id = get(input, "source_id").text;
    if (input.find("invalid_utf8_id"))
        request.source_id.assign(1, static_cast<char>(255));
    request.epoch = integer(get(input, "epoch"));
    request.source_bytes = integer(get(input, "source_bytes"));
    request.volume_offset = integer(get(input, "offset"));
    request.volume_bytes = integer(get(input, "length"));
    if (const auto *v = input.find("major"))
        request.major = small(*v);
    if (const auto *v = input.find("minor"))
        request.minor = small(*v);
    if (const auto *limits = input.find("limits")) {
#define LOAD(name)                                                                                 \
    if (const auto *v = limits->find(#name))                                                       \
    request.limits.name = static_cast<std::size_t>(integer(*v))
        LOAD(read_requests);
        LOAD(read_bytes);
        LOAD(retained_bytes);
        LOAD(attributes);
        LOAD(runs);
        LOAD(output_bytes);
#undef LOAD
    }
    std::vector<Region> regions;
    for (const auto &item : get(input, "regions").items)
        regions.push_back(Region{integer(get(item, "offset")), unhex(get(item, "hex"))});
    const auto original = regions;
    const auto held = request;
    auto requests = V::array();
    std::vector<std::unique_ptr<Guard>> guards;
    const auto *fault = input.find("fault");
    const auto mode = fault ? get(*fault, "mode").text : std::string();
    const auto fault_call = fault ? integer(get(*fault, "call")) : 0;
    disked::RegionReader reader;
    reader = [&](const de_byte_extent &extent) -> de_view {
        const auto first = native(extent.start), last = native(extent.end);
        need(extent.space &&
             std::string(extent.space->name, extent.space->name_length) == held.source_id);
        need(first >= held.volume_offset && last > first && last <= held.source_bytes &&
             last - first <= DE_NTFS_MAX_RECORD && last - held.volume_offset <= held.volume_bytes);
        requests.items.push_back(
            V::object().put("offset", exact(first)).put("bytes", exact(last - first)));
        const bool inject = requests.items.size() == fault_call;
        if (inject && mode == "throw")
            throw std::runtime_error("generated_reader_failure");
        if (inject && mode == "mutate-controls") {
            request.source_id = "changed";
            request.epoch = 999;
            request.volume_bytes = 512;
            request.limits.attributes = request.limits.runs = request.limits.read_requests = 1;
            request.major = 99;
            reader = {};
        }
        const auto length = static_cast<std::size_t>(last - first);
        auto buffer = std::vector<unsigned char>(length + (inject && mode == "oversize" ? 1 : 0));
        for (const auto &region : regions) {
            need(region.bytes.size() <= UINT64_MAX - region.start);
            const auto begin = std::max(first, region.start),
                       end = std::min(last, region.start + region.bytes.size());
            if (begin < end)
                std::copy(region.bytes.begin() + static_cast<std::size_t>(begin - region.start),
                          region.bytes.begin() + static_cast<std::size_t>(end - region.start),
                          buffer.begin() + static_cast<std::size_t>(begin - first));
        }
        if (inject && mode == "change") {
            const auto *at = fault->find("at");
            const auto index = at ? integer(*at) : 0;
            need(index < length);
            buffer[static_cast<std::size_t>(index)] ^= 1;
        }
        if (inject && mode == "null")
            return de_view{nullptr, length};
        guards.emplace_back(new Guard(buffer));
        return de_view{guards.back()->data, buffer.size() - (inject && mode == "short" ? 1 : 0)};
    };
    if (const auto *empty = input.find("empty_reader"))
        if (empty->boolean)
            reader = {};
    V report;
    std::string refusal;
    try {
        report = disked::observe_ntfs_bootstrap(request, reader);
    } catch (const std::exception &error) {
        refusal = error.what();
    }
    bool unchanged = original.size() == regions.size();
    for (std::size_t i = 0; unchanged && i < regions.size(); ++i)
        unchanged = original[i].start == regions[i].start && original[i].bytes == regions[i].bytes;
    // All callback storage is retired before the returned owned JSON is encoded.
    guards.clear();
    reader = {};
    regions.clear();
    return V::object()
        .put("report", std::move(report))
        .put("refusal", V::string(refusal))
        .put("requests", std::move(requests))
        .put("source_unchanged", V::boolean_value(unchanged));
}
int main() {
    try {
        process_rows(observe);
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
