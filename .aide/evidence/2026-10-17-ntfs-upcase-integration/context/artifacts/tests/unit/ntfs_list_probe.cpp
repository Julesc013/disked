#include "ntfs_probe_support.h"

static V size_value(std::size_t value) {
    de_u64 wide;
    need(de_u64_from_size(value, &wide) == DE_OK);
    return decimal(wide);
}
static V entry_value(const de_ntfs_attr_list_entry &entry) {
    return V::object()
        .put("type", number(entry.type))
        .put("record_length", number(entry.record_length))
        .put("name_length", number(entry.name_length))
        .put("name_offset", number(entry.name_offset))
        .put("lowest_vcn", decimal(entry.lowest_vcn))
        .put("segment_reference", decimal(entry.segment_reference))
        .put("record_number", decimal(entry.record_number))
        .put("sequence", number(entry.sequence))
        .put("attribute_id", number(entry.attribute_id))
        .put("raw_bytes", size_value(entry.raw.size))
        .put("name_hex", V::string(hex(entry.name.data, entry.name.size)))
        .put("present", V::boolean_value(entry.present != 0))
        .put("envelope_valid", V::boolean_value(entry.envelope_valid != 0))
        .put("issues", number(entry.issues));
}
static V run(const V &request) {
    const auto bytes = unhex(get(request, "hex"), 1048576);
    Guard input(bytes);
    const de_view raw{input.data, bytes.size()};
    de_ntfs_attr_list_cursor cursor;
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char before[sizeof(cursor)];
    std::memcpy(before, &cursor, sizeof(cursor));
    const auto status =
        de_ntfs_attr_list_begin(&raw, small(get(request, "major")), small(get(request, "minor")),
                                small(get(request, "budget")), &cursor);
    auto result = V::object()
                      .put("init_status", number(status))
                      .put("cursor_unchanged",
                           V::boolean_value(std::memcmp(before, &cursor, sizeof(cursor)) == 0));
    if (status == DE_OK) {
        auto rows = V::array();
        bool empty_unchanged = false;
        for (unsigned i = 0; i < 4098; ++i) {
            de_ntfs_attr_list_entry entry;
            std::memset(&entry, 0xa5, sizeof(entry));
            unsigned char entry_before[sizeof(entry)], cursor_before[sizeof(cursor)];
            std::memcpy(entry_before, &entry, sizeof(entry));
            std::memcpy(cursor_before, &cursor, sizeof(cursor));
            const auto next = de_ntfs_attr_list_next(&cursor, &entry);
            if (next == DE_EMPTY) {
                need(std::memcmp(entry_before, &entry, sizeof(entry)) == 0 &&
                     std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0);
                need(de_ntfs_attr_list_next(&cursor, &entry) == DE_EMPTY);
                need(std::memcmp(entry_before, &entry, sizeof(entry)) == 0 &&
                     std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0);
                empty_unchanged = true;
                break;
            }
            need(next == DE_OK && i < 4097);
            rows.items.push_back(entry_value(entry));
        }
        need(empty_unchanged);
        result.put("items", std::move(rows))
            .put("count", number(cursor.count))
            .put("offset", size_value(cursor.offset))
            .put("issues", number(cursor.issues))
            .put("terminated", V::boolean_value(cursor.terminated != 0))
            .put("stopped", V::boolean_value(cursor.stopped != 0))
            .put("empty_unchanged", V::boolean_value(empty_unchanged));
    }
    result.put("source_unchanged",
               V::boolean_value(bytes.empty() ||
                                std::memcmp(input.data, bytes.data(), bytes.size()) == 0));
    return result;
}
static void invalid_next(de_ntfs_attr_list_cursor cursor) {
    de_ntfs_attr_list_entry entry;
    std::memset(&entry, 0xa5, sizeof(entry));
    unsigned char before[sizeof(cursor)], entry_before[sizeof(entry)];
    std::memcpy(before, &cursor, sizeof(cursor));
    std::memcpy(entry_before, &entry, sizeof(entry));
    need(de_ntfs_attr_list_next(&cursor, &entry) == DE_INVALID);
    need(std::memcmp(before, &cursor, sizeof(cursor)) == 0 &&
         std::memcmp(entry_before, &entry, sizeof(entry)) == 0);
}
static void api_checks() {
    de_ntfs_attr_list_cursor cursor;
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char before[sizeof(cursor)];
    std::memcpy(before, &cursor, sizeof(cursor));
    const de_view empty{nullptr, 0}, invalid{nullptr, 1};
    need(de_ntfs_attr_list_begin(nullptr, 3, 1, 1, &cursor) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&empty, 3, 1, 1, nullptr) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&invalid, 3, 1, 1, &cursor) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&empty, 2, 1, 1, &cursor) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&empty, 3, 2, 1, &cursor) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&empty, 3, 1, 0, &cursor) == DE_BOUNDS);
    need(de_ntfs_attr_list_begin(&empty, 3, 1, 4097, &cursor) == DE_BOUNDS);
    need(std::memcmp(before, &cursor, sizeof(cursor)) == 0);
    need(de_ntfs_attr_list_next(nullptr, nullptr) == DE_INVALID);
    need(de_ntfs_attr_list_next(&cursor, nullptr) == DE_INVALID);
    need(de_ntfs_attr_list_begin(&empty, 3, 0, 1, &cursor) == DE_OK);
    auto changed = cursor;
    changed.offset = 1;
    invalid_next(changed);
    changed = cursor;
    changed.limit = 0;
    invalid_next(changed);
    changed = cursor;
    changed.count = 2;
    invalid_next(changed);
    changed = cursor;
    changed.value = invalid;
    invalid_next(changed);
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
