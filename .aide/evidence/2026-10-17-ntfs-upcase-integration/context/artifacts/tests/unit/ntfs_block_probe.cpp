#include "ntfs_probe_support.h"

static de_u32 dword_value(const V &v) {
    need(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    const auto n = std::stoull(v.text);
    need(n <= 0xffffffffULL);
    return static_cast<de_u32>(n);
}
static V observe(const de_ntfs_index_block &b) {
    return V::object()
        .put("fields_present", V::boolean_value(b.fields_present != 0))
        .put("fixups_valid", V::boolean_value(b.fixups_valid != 0))
        .put("envelope_valid", V::boolean_value(b.envelope_valid != 0))
        .put("issues", number(b.issues))
        .put("usa_offset", number(b.usa_offset))
        .put("usa_count", number(b.usa_count))
        .put("update_sequence", number(b.update_sequence))
        .put("strides", number(b.strides))
        .put("mismatched_tails", number(b.mismatched_tails))
        .put("log_sequence", decimal(b.log_sequence))
        .put("vbn", decimal(b.vbn))
        .put("first", number(b.first_offset))
        .put("used", number(b.used_bytes))
        .put("allocated", number(b.allocated_bytes))
        .put("flags", number(b.flags));
}
static V run(const V &row) {
    const auto bytes = unhex(get(row, "hex"));
    Guard source(bytes);
    const auto major = small(get(row, "major")), minor = small(get(row, "minor"));
    const auto expected = dword_value(get(row, "expected"));
    de_u64 vbn;
    const auto &vbn_text = get(row, "vbn").text;
    need(de_u64_parse(vbn_text.c_str(), vbn_text.size(), &vbn) == DE_OK);
    const auto alias = get(row, "alias").text;
    need(alias == "none" || alias == "same" || alias == "forward" || alias == "backward");
    std::vector<unsigned char> shared(bytes.size() * 2 + 32, 0xa5);
    if (!bytes.empty())
        std::memcpy(shared.data() + 8, bytes.data(), bytes.size());
    Guard output(std::vector<unsigned char>(bytes.size() + 16, 0xa5), false);
    const de_view raw{alias == "none" ? source.data : shared.data() + 8, bytes.size()};
    unsigned char *target = output.data;
    if (alias != "none")
        target = shared.data() + (alias == "same" ? 8 : alias == "forward" ? 9 : 7);
    const de_buffer destination{target, small(get(row, "capacity"))};
    need(destination.size <= bytes.size() + 16);
    de_ntfs_index_block block;
    std::memset(&block, 0xa5, sizeof(block));
    unsigned char before[sizeof(block)];
    std::memcpy(before, &block, sizeof(block));
    const auto status = de_ntfs_index_block_read(&raw, major, minor, expected, &vbn, &block);
    auto result = V::object().put("status", number(status));
    result.put("observe_unchanged",
               V::boolean_value(std::memcmp(before, &block, sizeof(block)) == 0));
    if (status == DE_OK)
        result.put("block", observe(block));
    std::memset(&block, 0xa5, sizeof(block));
    de_ntfs_index_cursor cursor;
    std::memset(&cursor, 0xa5, sizeof(cursor));
    unsigned char cursor_before[sizeof(cursor)];
    std::memcpy(cursor_before, &cursor, sizeof(cursor));
    const auto shared_before = shared;
    const bool begin = get(row, "mode").text == "begin";
    const auto restored =
        begin
            ? de_ntfs_index_block_begin(&raw, major, minor, expected, &vbn, &destination,
                                        small(get(row, "budget")), &block, &cursor)
            : de_ntfs_index_block_restore(&raw, major, minor, expected, &vbn, &destination, &block);
    result.put("restore_status", number(restored))
        .put("restore_observation_unchanged",
             V::boolean_value(std::memcmp(before, &block, sizeof(block)) == 0))
        .put("cursor_unchanged",
             V::boolean_value(std::memcmp(cursor_before, &cursor, sizeof(cursor)) == 0))
        .put("input_unchanged",
             V::boolean_value(bytes.empty() ||
                              std::memcmp(raw.data, bytes.data(), bytes.size()) == 0));
    bool unchanged = shared == shared_before;
    if (alias == "none") {
        for (std::size_t i = 0; i < bytes.size() + 16; ++i)
            unchanged = unchanged && output.data[i] == 0xa5;
    }
    result.put("output_unchanged", V::boolean_value(unchanged));
    if (restored == DE_OK) {
        result.put("restored_hex", V::string(hex(target, bytes.size())));
        bool tail = true;
        for (std::size_t i = bytes.size(); i < bytes.size() + 16; ++i)
            tail = tail && output.data[i] == 0xa5;
        need(tail);
        result.put("output_tail_unchanged", V::boolean_value(tail));
        need(block.raw.data == raw.data && block.raw.size == raw.size);
        if (begin) {
            need(cursor.value.data == target + 24 + block.first_offset);
            need(cursor.value.size == block.used_bytes - block.first_offset);
            auto items = V::array();
            bool done = false;
            for (unsigned i = 0; i < 4098; ++i) {
                de_ntfs_index_entry item;
                std::memset(&item, 0xa5, sizeof(item));
                unsigned char entry_before[sizeof(item)], state_before[sizeof(cursor)];
                std::memcpy(entry_before, &item, sizeof(item));
                std::memcpy(state_before, &cursor, sizeof(cursor));
                const auto next = de_ntfs_index_next(&cursor, &item);
                if (next == DE_EMPTY) {
                    need(std::memcmp(entry_before, &item, sizeof(item)) == 0 &&
                         std::memcmp(state_before, &cursor, sizeof(cursor)) == 0);
                    need(de_ntfs_index_next(&cursor, &item) == DE_EMPTY);
                    need(std::memcmp(entry_before, &item, sizeof(item)) == 0 &&
                         std::memcmp(state_before, &cursor, sizeof(cursor)) == 0);
                    done = true;
                    break;
                }
                need(next == DE_OK);
                items.items.push_back(
                    V::object()
                        .put("issues", number(item.issues))
                        .put("present", V::boolean_value(item.present != 0))
                        .put("end", V::boolean_value(item.end_marker != 0))
                        .put("child", decimal(item.child_vbn))
                        .put("reference", decimal(item.segment_reference))
                        .put("name_hex",
                             V::string(hex(item.filename.name.data, item.filename.name.size))));
            }
            need(done);
            result.put("items", std::move(items))
                .put("entry_count", number(cursor.count))
                .put("entry_issues", number(cursor.issues))
                .put("terminated", V::boolean_value(cursor.terminated != 0));
        }
    }
    return result;
}

static void api_checks() {
    de_ntfs_index_block b;
    de_ntfs_index_cursor c;
    std::memset(&b, 0xa5, sizeof(b));
    std::memset(&c, 0xa5, sizeof(c));
    unsigned char before[sizeof(b)], state[sizeof(c)], bytes[16];
    std::memcpy(before, &b, sizeof(b));
    std::memcpy(state, &c, sizeof(c));
    std::memset(bytes, 0xa5, sizeof(bytes));
    const de_view empty{nullptr, 0}, bad{nullptr, 1};
    const de_buffer output{bytes, sizeof(bytes)}, invalid{nullptr, 1};
    const de_u64 vbn{{0, 0, 0, 0}};
    need(de_ntfs_index_block_read(nullptr, 3, 1, 512, &vbn, &b) == DE_INVALID);
    need(de_ntfs_index_block_read(&bad, 3, 1, 512, &vbn, &b) == DE_INVALID);
    need(de_ntfs_index_block_read(&empty, 3, 1, 512, nullptr, &b) == DE_INVALID);
    need(de_ntfs_index_block_read(&empty, 3, 1, 512, &vbn, nullptr) == DE_INVALID);
    need(de_ntfs_index_block_restore(&empty, 3, 1, 512, &vbn, nullptr, &b) == DE_INVALID);
    need(de_ntfs_index_block_restore(&empty, 3, 1, 512, &vbn, &invalid, &b) == DE_INVALID);
    need(de_ntfs_index_block_begin(&empty, 3, 1, 512, &vbn, &output, 1, &b, nullptr) == DE_INVALID);
    need(de_ntfs_index_block_begin(&empty, 3, 1, 512, &vbn, &output, 0, &b, &c) == DE_BOUNDS);
    need(de_ntfs_index_block_begin(&empty, 3, 1, 512, &vbn, &output, 4097, &b, &c) == DE_BOUNDS);
    need(std::memcmp(before, &b, sizeof(b)) == 0 && std::memcmp(state, &c, sizeof(c)) == 0);
    for (auto byte : bytes)
        need(byte == 0xa5);
}
int main() {
    try {
        api_checks();
        process_rows(run);
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
