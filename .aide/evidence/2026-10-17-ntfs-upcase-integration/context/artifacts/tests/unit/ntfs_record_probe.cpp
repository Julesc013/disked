#include "ntfs_probe_support.h"
static V run(const V &row) {
    const auto bytes = unhex(get(row, "hex"));
    const auto major = small(get(row, "major")), minor = small(get(row, "minor"));
    const auto *mode = row.find("alias");
    const std::string alias = mode ? mode->text : "none";
    need(alias == "none" || alias == "same" || alias == "forward" || alias == "backward");
    Guard guard(bytes);
    std::vector<unsigned char> shared(bytes.size() * 2 + 32, 0xa5),
        destination(bytes.size() + 16, 0xa5);
    if (!bytes.empty())
        std::memcpy(shared.data() + 8, bytes.data(), bytes.size());
    de_view view{alias == "none" ? guard.data : shared.data() + 8, bytes.size()};
    de_ntfs_record observation;
    std::memset(&observation, 0xa5, sizeof(observation));
    unsigned char before[sizeof(observation)];
    std::memcpy(before, &observation, sizeof(observation));
    const int status = de_ntfs_record_read(&view, major, minor, &observation);
    V result = V::object()
                   .put("status", number(status))
                   .put("observe_unchanged",
                        V::boolean_value(std::memcmp(&before, &observation, sizeof(before)) == 0));
    if (!status)
        result.put("issues", number(observation.issues))
            .put("fields_present", V::boolean_value(observation.fields_present != 0))
            .put("fixups_valid", V::boolean_value(observation.fixups_valid != 0))
            .put("envelope_valid", V::boolean_value(observation.envelope_valid != 0))
            .put("mismatched_tails", number(observation.mismatched_tails))
            .put("strides", number(observation.strides))
            .put("usa_offset", number(observation.usa_offset))
            .put("usa_count", number(observation.usa_count))
            .put("update_sequence", number(observation.update_sequence))
            .put("sequence", number(observation.sequence))
            .put("links", number(observation.links))
            .put("flags", number(observation.flags))
            .put("in_use", V::boolean_value(observation.in_use != 0))
            .put("name_index_present", V::boolean_value(observation.name_index_present != 0))
            .put("attribute_offset", number(observation.attribute_offset))
            .put("used_bytes", number(observation.used_bytes))
            .put("allocated_bytes", number(observation.allocated_bytes))
            .put("next_attribute_id", number(observation.next_attribute_id))
            .put("log_sequence", decimal(observation.log_sequence))
            .put("base_reference", decimal(observation.base_reference));
    const auto *capacity = row.find("capacity");
    const std::size_t cap = capacity ? small(*capacity) : bytes.size();
    need(cap <= destination.size());
    unsigned char *target = destination.data();
    if (alias != "none")
        target = shared.data() + (alias == "backward" ? 7 : alias == "forward" ? 9 : 8);
    de_buffer output{target, cap};
    de_ntfs_record restored;
    std::memset(&restored, 0xa5, sizeof(restored));
    unsigned char restored_before[sizeof(restored)];
    std::memcpy(restored_before, &restored, sizeof(restored));
    const auto shared_before = shared;
    const auto destination_before = destination;
    const int restored_status = de_ntfs_record_restore(&view, major, minor, &output, &restored);
    result.put("restore_status", number(restored_status))
        .put("restore_observation_unchanged",
             V::boolean_value(std::memcmp(&restored, &restored_before, sizeof(restored)) == 0))
        .put("output_unchanged",
             V::boolean_value(alias == "none" ? destination == destination_before
                                              : shared == shared_before))
        .put("input_unchanged",
             V::boolean_value(bytes.empty() ||
                              std::memcmp(view.data, bytes.data(), bytes.size()) == 0));
    if (!restored_status)
        result.put("restored_hex", V::string(hex(target, bytes.size())))
            .put("output_tail_unchanged",
                 V::boolean_value(std::memcmp(destination.data() + bytes.size(),
                                              destination_before.data() + bytes.size(), 16) == 0));
    return result;
}
static void api_checks() {
    de_ntfs_record result;
    std::memset(&result, 0xa5, sizeof(result));
    unsigned char before[sizeof(result)];
    std::memcpy(before, &result, sizeof(result));
    unsigned char destination[32];
    std::memset(destination, 0xa5, sizeof(destination));
    const de_view empty{nullptr, 0}, invalid{nullptr, 1};
    const de_buffer output{destination, sizeof(destination)}, invalid_output{nullptr, 1};
    need(de_ntfs_record_read(nullptr, 3, 1, &result) == DE_INVALID);
    need(de_ntfs_record_read(&invalid, 3, 1, &result) == DE_INVALID);
    need(de_ntfs_record_read(&empty, 3, 1, nullptr) == DE_INVALID);
    need(de_ntfs_record_restore(nullptr, 3, 1, &output, &result) == DE_INVALID);
    need(de_ntfs_record_restore(&empty, 3, 1, nullptr, &result) == DE_INVALID);
    need(de_ntfs_record_restore(&empty, 3, 1, &invalid_output, &result) == DE_INVALID);
    need(de_ntfs_record_restore(&empty, 3, 1, &output, nullptr) == DE_INVALID);
    need(std::memcmp(before, &result, sizeof(result)) == 0);
    for (const auto byte : destination)
        need(byte == 0xa5);
    need(de_ntfs_record_read(&empty, 3, 1, &result) == DE_OK);
    need(result.issues == (DE_NTFS_LENGTH | DE_NTFS_TRUNCATED));
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
