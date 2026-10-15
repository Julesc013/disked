#include "ntfs_probe_support.h"

static de_u64 integer(const V &value) {
    de_u64 result;
    need(value.kind == V::Kind::string);
    need(de_u64_parse(value.text.data(), value.text.size(), &result) == DE_OK);
    return result;
}
static V attribute(const de_ntfs_attribute &value) {
    auto row = V::object();
#define FIELD(name) row.put(#name, number(value.name))
    FIELD(type);
    FIELD(record_length);
    FIELD(form);
    FIELD(name_length);
    FIELD(name_offset);
    FIELD(flags);
    FIELD(instance);
    FIELD(value_length);
    FIELD(value_offset);
    FIELD(resident_flags);
    FIELD(mapping_offset);
    FIELD(compression_unit);
    FIELD(issues);
#undef FIELD
#define FIELD(name) row.put(#name, decimal(value.name))
    FIELD(lowest_vcn);
    FIELD(highest_vcn);
    FIELD(cluster_span);
    FIELD(allocated_size);
    FIELD(data_size);
    FIELD(initialized_size);
    FIELD(total_allocated);
#undef FIELD
#define FIELD(name) row.put(#name, V::boolean_value(value.name != 0))
    FIELD(present);
    FIELD(end_marker);
    FIELD(variant_fields);
    FIELD(envelope_valid);
    FIELD(sizes_applicable);
    FIELD(has_total_allocated);
    FIELD(empty_stream);
    FIELD(ordinary_mapping);
#undef FIELD
    row.put("name_hex", V::string(hex(value.name.data, value.name.size)))
        .put("value_hex", V::string(hex(value.value.data, value.value.size)))
        .put("mapping_hex", V::string(hex(value.mapping.data, value.mapping.size)));
    return row;
}
static V attributes(const V &request) {
    const auto bytes = unhex(get(request, "hex"));
    const auto budget = small(get(request, "budget"));
    const auto major = small(get(request, "major")), minor = small(get(request, "minor"));
    const auto *alias_field = request.find("alias");
    const std::string alias = alias_field ? alias_field->text : "none";
    need(alias == "none" || alias == "same" || alias == "forward" || alias == "backward");
    Guard input(bytes), output(std::vector<unsigned char>(bytes.size(), 0xa5), false);
    std::vector<unsigned char> shared(bytes.size() * 2 + 32, 0xa5);
    if (!bytes.empty())
        std::memcpy(shared.data() + 8, bytes.data(), bytes.size());
    const auto shared_before = shared;
    const de_view original{alias == "none" ? input.data : shared.data() + 8, bytes.size()};
    const auto *capacity_field = request.find("capacity");
    const std::size_t capacity = capacity_field ? small(*capacity_field) : bytes.size();
    need(capacity <= bytes.size());
    unsigned char *target = alias == "none" ? output.data
                                            : shared.data() + (alias == "backward"  ? 7
                                                               : alias == "forward" ? 9
                                                                                    : 8);
    const de_buffer restored{target, capacity};
    de_ntfs_attr_cursor cursor;
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char before[sizeof(cursor)];
    std::memcpy(before, &cursor, sizeof(cursor));
    const int status =
        de_ntfs_attributes_begin(&original, major, minor, &restored, budget, &cursor);
    auto result = V::object()
                      .put("init_status", number(status))
                      .put("cursor_unchanged",
                           V::boolean_value(std::memcmp(before, &cursor, sizeof(cursor)) == 0));
    bool unchanged = true;
    if (alias == "none") {
        for (std::size_t i = 0; i < bytes.size(); ++i)
            unchanged = unchanged && output.data[i] == 0xa5;
    } else
        unchanged = shared == shared_before;
    result.put("destination_unchanged", V::boolean_value(unchanged));
    if (!status) {
        if (alias == "none")
            output.seal();
        auto rows = V::array();
        for (unsigned i = 0; i < 4098; ++i) {
            de_ntfs_attribute item;
            std::memset(&item, 0xa5, sizeof(item));
            unsigned char item_before[sizeof(item)], cursor_before[sizeof(cursor)];
            std::memcpy(item_before, &item, sizeof(item));
            std::memcpy(cursor_before, &cursor, sizeof(cursor));
            const int next = de_ntfs_attributes_next(&cursor, &item);
            if (next == DE_EMPTY) {
                need(std::memcmp(item_before, &item, sizeof(item)) == 0 &&
                     std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0);
                break;
            }
            need(next == DE_OK && i < 4097);
            rows.items.push_back(attribute(item));
        }
        result.put("items", std::move(rows))
            .put("count", number(cursor.count))
            .put("issues", number(cursor.issues))
            .put("offset", number(static_cast<de_u32>(cursor.offset)))
            .put("terminated", V::boolean_value(cursor.terminated != 0))
            .put("stopped", V::boolean_value(cursor.stopped != 0));
    }
    result.put("source_unchanged",
               V::boolean_value(bytes.empty() ||
                                std::memcmp(original.data, bytes.data(), bytes.size()) == 0));
    return result;
}
static V runs(const V &request) {
    const auto bytes = unhex(get(request, "hex"));
    Guard guard(bytes);
    const de_view pairs{guard.data, bytes.size()};
    const auto first = integer(get(request, "first")), count = integer(get(request, "count")),
               volume = integer(get(request, "volume"));
    const auto sparse = small(get(request, "sparse")), budget = small(get(request, "budget"));
    de_ntfs_run_cursor cursor;
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char before[sizeof(cursor)];
    std::memcpy(before, &cursor, sizeof(cursor));
    const int status = de_ntfs_runs_begin(&pairs, &first, &count, &volume, static_cast<int>(sparse),
                                          budget, &cursor);
    auto result = V::object()
                      .put("init_status", number(status))
                      .put("cursor_unchanged",
                           V::boolean_value(std::memcmp(before, &cursor, sizeof(cursor)) == 0));
    if (!status) {
        auto rows = V::array();
        for (unsigned i = 0; i < 4098; ++i) {
            de_ntfs_run item;
            std::memset(&item, 0xa5, sizeof(item));
            unsigned char item_before[sizeof(item)], cursor_before[sizeof(cursor)];
            std::memcpy(item_before, &item, sizeof(item));
            std::memcpy(cursor_before, &cursor, sizeof(cursor));
            const int next = de_ntfs_runs_next(&cursor, &item);
            if (next == DE_EMPTY) {
                need(std::memcmp(item_before, &item, sizeof(item)) == 0 &&
                     std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0);
                break;
            }
            need(next == DE_OK && i < 4097);
            rows.items.push_back(
                V::object()
                    .put("issues", number(item.issues))
                    .put("length_width", number(item.length_width))
                    .put("offset_width", number(item.offset_width))
                    .put("vcn", decimal(item.vcn))
                    .put("next_vcn", decimal(item.next_vcn))
                    .put("length", decimal(item.length))
                    .put("lcn", decimal(item.lcn))
                    .put("lcn_end", decimal(item.lcn_end))
                    .put("present", V::boolean_value(item.present != 0))
                    .put("end_marker", V::boolean_value(item.end_marker != 0))
                    .put("sparse", V::boolean_value(item.sparse != 0))
                    .put("negative_delta", V::boolean_value(item.negative_delta != 0))
                    .put("valid", V::boolean_value(item.valid != 0)));
        }
        result.put("items", std::move(rows))
            .put("count", number(cursor.count))
            .put("issues", number(cursor.issues))
            .put("offset", number(static_cast<de_u32>(cursor.offset)))
            .put("next_vcn", decimal(cursor.next_vcn))
            .put("previous_lcn", decimal(cursor.previous_lcn))
            .put("terminated", V::boolean_value(cursor.terminated != 0))
            .put("stopped", V::boolean_value(cursor.stopped != 0));
    }
    result.put("source_unchanged",
               V::boolean_value(bytes.empty() ||
                                std::memcmp(pairs.data, bytes.data(), bytes.size()) == 0));
    return result;
}
static V run(const V &request) {
    const auto &op = get(request, "op");
    need(op.kind == V::Kind::string);
    if (op.text == "attrs")
        return attributes(request);
    need(op.text == "runs");
    return runs(request);
}
static void api_checks() {
    de_ntfs_attr_cursor attrs;
    de_ntfs_run_cursor mappings;
    std::memset(&attrs, 0xa5, sizeof(attrs));
    std::memset(&mappings, 0xa5, sizeof(mappings));
    unsigned char attrs_before[sizeof(attrs)], runs_before[sizeof(mappings)];
    std::memcpy(attrs_before, &attrs, sizeof(attrs));
    std::memcpy(runs_before, &mappings, sizeof(mappings));
    unsigned char destination[32];
    std::memset(destination, 0xa5, sizeof(destination));
    const de_view empty{nullptr, 0}, invalid{nullptr, 1};
    const de_buffer output{destination, sizeof(destination)};
    const auto zero = de_u64_from_u32(0), one = de_u64_from_u32(1);
    need(de_ntfs_attributes_begin(nullptr, 3, 1, &output, 1, &attrs) == DE_INVALID);
    need(de_ntfs_attributes_begin(&empty, 3, 1, nullptr, 1, &attrs) == DE_INVALID);
    need(de_ntfs_attributes_begin(&empty, 3, 1, &output, 1, nullptr) == DE_INVALID);
    need(de_ntfs_attributes_begin(&invalid, 3, 1, &output, 1, &attrs) == DE_INVALID);
    need(de_ntfs_attributes_begin(&empty, 3, 1, &output, 0, &attrs) == DE_BOUNDS);
    need(de_ntfs_runs_begin(nullptr, &zero, &one, &one, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, nullptr, &one, &one, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, nullptr, &one, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, &one, nullptr, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, &one, &one, 0, 1, nullptr) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, &one, &zero, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&invalid, &zero, &one, &one, 0, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, &one, &one, 2, 1, &mappings) == DE_INVALID);
    need(de_ntfs_runs_begin(&empty, &zero, &one, &one, 0, 0, &mappings) == DE_BOUNDS);
    need(de_ntfs_attributes_next(nullptr, nullptr) == DE_INVALID);
    need(de_ntfs_runs_next(nullptr, nullptr) == DE_INVALID);
    need(std::memcmp(attrs_before, &attrs, sizeof(attrs)) == 0 &&
         std::memcmp(runs_before, &mappings, sizeof(mappings)) == 0);
    for (const auto byte : destination)
        need(byte == 0xa5);
}
int main() {
    try {
        api_checks();
        process_rows(run);
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
