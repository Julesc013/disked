#include "runtime/capture/ntfs_stream.h"
#include "ntfs_probe_support.h"
#include <memory>

static std::uint64_t integer(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
static disked::NtfsStreamContext context(const V &input) {
    disked::NtfsStreamContext value;
    value.source_id = get(input, "source_id").text;
    value.epoch = integer(get(input, "epoch"));
    value.volume_offset = integer(get(input, "offset"));
    value.volume_bytes = integer(get(input, "length"));
    return value;
}
static V run(const V &input) {
    disked::NtfsStreamJoinRequest request;
    request.context = context(get(input, "context"));
    request.base_reference = integer(get(input, "base"));
    request.volume_clusters = integer(get(input, "clusters"));
    if (const auto *v = input.find("cluster_bytes"))
        request.cluster_bytes = static_cast<std::uint32_t>(integer(*v));
    if (const auto *v = input.find("record_bytes"))
        request.record_bytes = static_cast<std::uint32_t>(integer(*v));
    if (const auto *v = input.find("type"))
        request.type = static_cast<std::uint32_t>(integer(*v));
    if (const auto *v = input.find("major"))
        request.major = small(*v);
    if (const auto *v = input.find("minor"))
        request.minor = small(*v);
    request.name = unhex(get(input, "name"));
    if (const auto *limits = input.find("limits")) {
#define LOAD(name)                                                                                 \
    if (const auto *v = limits->find(#name))                                                       \
    request.limits.name = static_cast<std::size_t>(integer(*v))
        LOAD(records);
        LOAD(record_bytes);
        LOAD(attributes);
        LOAD(list_entries);
        LOAD(runs);
        LOAD(output_bytes);
#undef LOAD
    }
    std::vector<std::vector<unsigned char>> originals;
    std::vector<std::unique_ptr<Guard>> guards;
    std::vector<disked::NtfsCapturedRecord> records;
    for (const auto &row : get(input, "records").items) {
        originals.push_back(unhex(get(row, "hex")));
        guards.emplace_back(new Guard(originals.back()));
        disked::NtfsCapturedRecord record;
        record.number = integer(get(row, "number"));
        record.context = row.find("context") ? context(get(row, "context")) : request.context;
        record.bytes = de_view{guards.back()->data, originals.back().size()};
        if (const auto *null_view = row.find("null_view"))
            if (null_view->boolean)
                record.bytes.data = nullptr;
        records.push_back(record);
    }
    auto result = V::object();
    try {
        auto joined = disked::join_ntfs_stream(request, records);
        for (std::size_t i = 0; i < records.size(); ++i)
            need(originals[i].empty() ||
                 !std::memcmp(guards[i]->data, originals[i].data(), originals[i].size()));
        guards.clear(); // The typed stream and report must outlive every borrowed input.
        result.put("refusal", V::string(""))
            .put("observation", std::move(joined.observation))
            .put("usable", V::boolean_value(joined.stream != nullptr));
        if (joined.stream) {
            const auto &s = *joined.stream;
            auto parts = V::array(), runs = V::array();
            for (const auto &p : s.parts)
                parts.items.push_back(V::object()
                                          .put("reference", exact(p.reference))
                                          .put("instance", exact(p.instance))
                                          .put("lowest_vcn", exact(p.lowest_vcn))
                                          .put("highest_vcn", exact(p.highest_vcn)));
            for (const auto &r : s.runs)
                runs.items.push_back(V::object()
                                         .put("vcn", exact(r.vcn))
                                         .put("clusters", exact(r.clusters))
                                         .put("lcn", exact(r.lcn)));
            result.put("stream", V::object()
                                     .put("resident", V::boolean_value(s.resident))
                                     .put("type", exact(s.type))
                                     .put("name", V::string(hex(s.name.data(), s.name.size())))
                                     .put("value", V::string(hex(s.value.data(), s.value.size())))
                                     .put("allocated_bytes", exact(s.allocated_bytes))
                                     .put("data_bytes", exact(s.data_bytes))
                                     .put("initialized_bytes", exact(s.initialized_bytes))
                                     .put("parts", std::move(parts))
                                     .put("runs", std::move(runs)));
        }
    } catch (const std::exception &failure) {
        result.put("refusal", V::string(failure.what())).put("usable", V::boolean_value(false));
    }
    for (std::size_t i = 0; i < guards.size(); ++i)
        need(originals[i].empty() ||
             !std::memcmp(guards[i]->data, originals[i].data(), originals[i].size()));
    return result.put("source_unchanged", V::boolean_value(true));
}
int main() {
    try {
        process_rows(run);
        return 0;
    } catch (const std::exception &failure) {
        std::cerr << failure.what() << '\n';
        return 2;
    }
}
