#include "runtime/capture/ntfs_names.h"
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
    disked::NtfsFilenameRequest request;
    request.context = context(get(input, "context"));
    request.base_reference = integer(get(input, "base"));
    request.volume_clusters = integer(get(input, "clusters"));
    if (const auto *v = input.find("cluster_bytes"))
        request.cluster_bytes = static_cast<std::uint32_t>(integer(*v));
    if (const auto *v = input.find("record_bytes"))
        request.record_bytes = static_cast<std::uint32_t>(integer(*v));
    if (const auto *v = input.find("major"))
        request.major = small(*v);
    if (const auto *v = input.find("minor"))
        request.minor = small(*v);
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
        LOAD(list_bytes);
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
    disked::NtfsCapturedAttributeList list;
    std::unique_ptr<Guard> list_guard;
    std::vector<unsigned char> list_original;
    if (const auto *capture = input.find("list_capture")) {
        list_original = unhex(get(*capture, "hex"), 1048576);
        list_guard.reset(new Guard(list_original));
        list.context =
            capture->find("context") ? context(get(*capture, "context")) : request.context;
        list.base_reference = integer(get(*capture, "base"));
        list.instance = small(get(*capture, "instance"));
        list.base_record_sha256 = get(*capture, "base_sha256").text;
        list.value = de_view{list_guard->data, list_original.size()};
    }
    try {
        auto joined =
            disked::collect_ntfs_filenames(request, records, list_guard ? &list : nullptr);
        for (std::size_t i = 0; i < records.size(); ++i)
            need(originals[i].empty() ||
                 !std::memcmp(guards[i]->data, originals[i].data(), originals[i].size()));
        guards.clear(); // The typed names and report must outlive every borrowed input.
        if (list_guard) {
            need(list_original.empty() ||
                 !std::memcmp(list_guard->data, list_original.data(), list_original.size()));
            list_guard.reset();
        }
        auto missing = V::array();
        for (const auto reference : joined.required_records)
            missing.items.push_back(exact(reference));
        result.put("required_records", std::move(missing));
        result.put("refusal", V::string(""))
            .put("observation", std::move(joined.observation))
            .put("usable", V::boolean_value(joined.names != nullptr));
        if (joined.names) {
            auto names = V::array();
            for (const auto &n : *joined.names)
                names.items.push_back(
                    V::object()
                        .put("reference", exact(n.reference))
                        .put("instance", exact(n.instance))
                        .put("resident_flags", exact(n.resident_flags))
                        .put("parent_reference", exact(n.parent_reference))
                        .put("namespace", exact(n.namespace_code))
                        .put("name", V::string(hex(n.name.data(), n.name.size())))
                        .put("value", V::string(hex(n.value.data(), n.value.size()))));
            result.put("names", std::move(names));
        }
    } catch (const std::exception &failure) {
        result.put("refusal", V::string(failure.what())).put("usable", V::boolean_value(false));
    }
    for (std::size_t i = 0; i < guards.size(); ++i)
        need(originals[i].empty() ||
             !std::memcmp(guards[i]->data, originals[i].data(), originals[i].size()));
    if (list_guard)
        need(list_original.empty() ||
             !std::memcmp(list_guard->data, list_original.data(), list_original.size()));
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
