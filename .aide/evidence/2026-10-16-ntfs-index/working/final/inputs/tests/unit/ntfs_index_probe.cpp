#include "ntfs_probe_support.h"

static V size_value(std::size_t n) {
    return V::string(std::to_string(n));
}
static de_u32 dword_value(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    const auto n = std::stoull(v.text);
    need(n <= 0xffffffffULL);
    return static_cast<de_u32>(n);
}
static V name_value(const de_ntfs_filename &v) {
    return V::object()
        .put("raw_bytes", size_value(v.raw.size))
        .put("parent_reference", decimal(v.parent_reference))
        .put("parent_record", decimal(v.parent_record))
        .put("parent_sequence", number(v.parent_sequence))
        .put("duplicated_hex",
             V::string(hex(v.duplicated_information.data, v.duplicated_information.size)))
        .put("name_length", number(v.name_length))
        .put("namespace", number(v.namespace_code))
        .put("name_hex", V::string(hex(v.name.data, v.name.size)))
        .put("suffix_hex", V::string(hex(v.suffix.data, v.suffix.size)))
        .put("fields_present", V::boolean_value(v.fields_present != 0))
        .put("envelope_valid", V::boolean_value(v.envelope_valid != 0))
        .put("namespace_known", V::boolean_value(v.namespace_known != 0))
        .put("issues", number(v.issues));
}
static V root_value(const de_ntfs_index_root &v) {
    return V::object()
        .put("raw_bytes", size_value(v.raw.size))
        .put("type", number(v.type))
        .put("collation", number(v.collation))
        .put("index_bytes", number(v.index_bytes))
        .put("units", number(v.units_per_index))
        .put("flags", number(v.flags))
        .put("first", number(v.first_offset))
        .put("used", number(v.used_bytes))
        .put("allocated", number(v.allocated_bytes))
        .put("child_unit_bytes", number(v.child_unit_bytes))
        .put("fields_present", V::boolean_value(v.fields_present != 0))
        .put("envelope_valid", V::boolean_value(v.envelope_valid != 0))
        .put("geometry_matches", V::boolean_value(v.geometry_matches != 0))
        .put("directory_profile", V::boolean_value(v.directory_profile != 0))
        .put("issues", number(v.issues));
}
static V entry_value(const de_ntfs_index_entry &v) {
    return V::object()
        .put("raw_bytes", size_value(v.raw.size))
        .put("record_length", number(v.record_length))
        .put("key_length", number(v.key_length))
        .put("flags", number(v.flags))
        .put("segment_reference", decimal(v.segment_reference))
        .put("record_number", decimal(v.record_number))
        .put("sequence", number(v.sequence))
        .put("child_vbn", decimal(v.child_vbn))
        .put("key_hex", V::string(hex(v.key.data, v.key.size)))
        .put("padding_hex", V::string(hex(v.padding.data, v.padding.size)))
        .put("filename", name_value(v.filename))
        .put("present", V::boolean_value(v.present != 0))
        .put("end_marker", V::boolean_value(v.end_marker != 0))
        .put("has_child", V::boolean_value(v.has_child != 0))
        .put("envelope_valid", V::boolean_value(v.envelope_valid != 0))
        .put("issues", number(v.issues));
}
static V run(const V &request) {
    const auto bytes = unhex(get(request, "hex"), 1048576);
    Guard input(bytes);
    const de_view raw{input.data, bytes.size()};
    const auto major = small(get(request, "major")), minor = small(get(request, "minor"));
    auto result = V::object();
    if (get(request, "mode").text == "name") {
        de_ntfs_filename name;
        std::memset(&name, 0xa5, sizeof(name));
        unsigned char before[sizeof(name)];
        std::memcpy(before, &name, sizeof(name));
        const auto status = de_ntfs_filename_read(&raw, major, minor, &name);
        result.put("init_status", number(status))
            .put("outputs_unchanged",
                 V::boolean_value(std::memcmp(before, &name, sizeof(name)) == 0));
        if (status == DE_OK)
            result.put("name", name_value(name));
    } else {
        need(get(request, "mode").text == "index");
        de_ntfs_index_root root;
        de_ntfs_index_cursor cursor;
        std::memset(&root, 0xa5, sizeof(root));
        std::memset(&cursor, 0xa5, sizeof(cursor));
        unsigned char root_before[sizeof(root)], cursor_before[sizeof(cursor)];
        std::memcpy(root_before, &root, sizeof(root));
        std::memcpy(cursor_before, &cursor, sizeof(cursor));
        const auto status =
            de_ntfs_index_root_begin(&raw, major, minor, dword_value(get(request, "cluster")),
                                     dword_value(get(request, "index_bytes")),
                                     small(get(request, "budget")), &root, &cursor);
        result.put("init_status", number(status))
            .put("outputs_unchanged",
                 V::boolean_value(std::memcmp(root_before, &root, sizeof(root)) == 0 &&
                                  std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0));
        if (status == DE_OK) {
            result.put("root", root_value(root));
            auto items = V::array();
            bool completed = false;
            for (unsigned i = 0; i < 4098; ++i) {
                de_ntfs_index_entry entry;
                std::memset(&entry, 0xa5, sizeof(entry));
                unsigned char before_entry[sizeof(entry)], before_cursor[sizeof(cursor)];
                std::memcpy(before_entry, &entry, sizeof(entry));
                std::memcpy(before_cursor, &cursor, sizeof(cursor));
                const auto next = de_ntfs_index_next(&cursor, &entry);
                if (next == DE_EMPTY) {
                    need(std::memcmp(before_entry, &entry, sizeof(entry)) == 0 &&
                         std::memcmp(before_cursor, &cursor, sizeof(cursor)) == 0);
                    need(de_ntfs_index_next(&cursor, &entry) == DE_EMPTY);
                    need(std::memcmp(before_entry, &entry, sizeof(entry)) == 0 &&
                         std::memcmp(before_cursor, &cursor, sizeof(cursor)) == 0);
                    completed = true;
                    break;
                }
                need(next == DE_OK && i < 4097);
                items.items.push_back(entry_value(entry));
            }
            need(completed);
            result.put("items", std::move(items))
                .put("count", number(cursor.count))
                .put("offset", size_value(cursor.offset))
                .put("issues", number(cursor.issues))
                .put("terminated", V::boolean_value(cursor.terminated != 0))
                .put("stopped", V::boolean_value(cursor.stopped != 0))
                .put("empty_unchanged", V::boolean_value(completed));
        }
    }
    result.put("source_unchanged",
               V::boolean_value(bytes.empty() ||
                                std::memcmp(input.data, bytes.data(), bytes.size()) == 0));
    return result;
}
static void invalid_next(de_ntfs_index_cursor cursor) {
    de_ntfs_index_entry entry;
    std::memset(&entry, 0xa5, sizeof(entry));
    unsigned char before[sizeof(cursor)], before_entry[sizeof(entry)];
    std::memcpy(before, &cursor, sizeof(cursor));
    std::memcpy(before_entry, &entry, sizeof(entry));
    need(de_ntfs_index_next(&cursor, &entry) == DE_INVALID);
    need(std::memcmp(before, &cursor, sizeof(cursor)) == 0 &&
         std::memcmp(before_entry, &entry, sizeof(entry)) == 0);
}
static void api_checks() {
    const de_view empty{nullptr, 0}, invalid{nullptr, 1};
    de_ntfs_filename name;
    std::memset(&name, 0xa5, sizeof(name));
    unsigned char name_before[sizeof(name)];
    std::memcpy(name_before, &name, sizeof(name));
    need(de_ntfs_filename_read(nullptr, 3, 1, &name) == DE_INVALID);
    need(de_ntfs_filename_read(&invalid, 3, 1, &name) == DE_INVALID);
    need(de_ntfs_filename_read(&empty, 3, 2, &name) == DE_INVALID);
    need(de_ntfs_filename_read(&empty, 2, 0, &name) == DE_INVALID);
    need(de_ntfs_filename_read(&empty, 3, 0, nullptr) == DE_INVALID);
    need(std::memcmp(name_before, &name, sizeof(name)) == 0);
    de_ntfs_index_root root;
    de_ntfs_index_cursor cursor;
    std::memset(&root, 0xa5, sizeof(root));
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char root_before[sizeof(root)], cursor_before[sizeof(cursor)];
    std::memcpy(root_before, &root, sizeof(root));
    std::memcpy(cursor_before, &cursor, sizeof(cursor));
    need(de_ntfs_index_root_begin(nullptr, 3, 1, 4096, 4096, 1, &root, &cursor) == DE_INVALID);
    need(de_ntfs_index_root_begin(&invalid, 3, 1, 4096, 4096, 1, &root, &cursor) == DE_INVALID);
    need(de_ntfs_index_root_begin(&empty, 2, 0, 4096, 4096, 1, &root, &cursor) == DE_INVALID);
    need(de_ntfs_index_root_begin(&empty, 3, 2, 4096, 4096, 1, &root, &cursor) == DE_INVALID);
    need(de_ntfs_index_root_begin(&empty, 3, 1, 4096, 4096, 0, &root, &cursor) == DE_BOUNDS);
    need(de_ntfs_index_root_begin(&empty, 3, 1, 4096, 4096, 4097, &root, &cursor) == DE_BOUNDS);
    need(de_ntfs_index_root_begin(&empty, 3, 1, 4096, 4096, 1, nullptr, &cursor) == DE_INVALID);
    need(de_ntfs_index_root_begin(&empty, 3, 1, 4096, 4096, 1, &root, nullptr) == DE_INVALID);
    need(std::memcmp(root_before, &root, sizeof(root)) == 0 &&
         std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0);
    need(de_ntfs_index_root_begin(&empty, 3, 0, 4096, 4096, 1, &root, &cursor) == DE_OK);
    auto bad = cursor;
    bad.offset = 1;
    invalid_next(bad);
    bad = cursor;
    bad.count = 2;
    invalid_next(bad);
    bad = cursor;
    bad.limit = 0;
    invalid_next(bad);
    bad = cursor;
    bad.limit = 4097;
    invalid_next(bad);
    bad = cursor;
    bad.value = invalid;
    invalid_next(bad);
    bad = cursor;
    bad.major = 4;
    invalid_next(bad);
    bad = cursor;
    bad.minor = 2;
    invalid_next(bad);
    bad = cursor;
    bad.has_children = 2;
    invalid_next(bad);
    need(de_ntfs_index_next(nullptr, nullptr) == DE_INVALID);
    need(de_ntfs_index_next(&cursor, nullptr) == DE_INVALID);
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
