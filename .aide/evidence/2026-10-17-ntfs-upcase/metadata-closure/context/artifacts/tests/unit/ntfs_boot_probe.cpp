#include "ntfs_probe_support.h"

static V run(const V &row) {
    const auto bytes = unhex(get(row, "hex"));
    const auto major = small(get(row, "major")), minor = small(get(row, "minor"));
    const auto &text = get(row, "available");
    need(text.kind == V::Kind::string);
    de_u64 available;
    need(de_u64_parse(text.text.data(), text.text.size(), &available) == DE_OK);
    Guard guard(bytes);
    const de_view view{guard.data, bytes.size()};
    de_ntfs_boot observation;
    std::memset(&observation, 0xa5, sizeof(observation));
    unsigned char before[sizeof(observation)];
    std::memcpy(before, &observation, sizeof(observation));
    const int status = de_ntfs_boot_read(&view, &available, major, minor, &observation);
    auto result =
        V::object()
            .put("status", number(status))
            .put("result_unchanged",
                 V::boolean_value(std::memcmp(before, &observation, sizeof(observation)) == 0))
            .put("input_unchanged",
                 V::boolean_value(bytes.empty() ||
                                  std::memcmp(view.data, bytes.data(), bytes.size()) == 0));
    if (status)
        return result;
    result.put("issues", number(observation.issues));
#define FIELD(name) result.put(#name, number(observation.name))
    FIELD(bytes_per_sector);
    FIELD(cluster_code);
    FIELD(record_code);
    FIELD(index_code);
    FIELD(sectors_per_cluster);
    FIELD(cluster_bytes);
    FIELD(record_bytes);
    FIELD(index_bytes);
    FIELD(checksum);
    FIELD(calculated_checksum);
    FIELD(hidden_sectors);
    FIELD(marker);
    FIELD(sectors_per_track);
    FIELD(heads);
    FIELD(media_type);
#undef FIELD
#define FIELD(name) result.put(#name, decimal(observation.name))
    FIELD(sector_field);
    FIELD(mft_lcn);
    FIELD(mirror_lcn);
    FIELD(serial);
    FIELD(data_bytes);
    FIELD(media_span_bytes);
    FIELD(clusters);
    FIELD(mft0_offset);
    FIELD(mirror0_offset);
#undef FIELD
#define FIELD(name) result.put(#name, V::boolean_value(observation.name != 0))
    FIELD(fields_present);
    FIELD(complete_sector);
    FIELD(data_bound_known);
    FIELD(media_span_known);
    FIELD(record_size_known);
    FIELD(index_size_known);
    FIELD(record_budget_supported);
    FIELD(mft0_offset_known);
    FIELD(mirror0_offset_known);
    FIELD(seed_addresses_valid);
    FIELD(checksum_present);
    FIELD(checksum_matches);
    FIELD(geometry_valid);
    FIELD(bootstrap_usable);
#undef FIELD
    return result;
}

static void api_checks() {
    de_ntfs_boot result;
    std::memset(&result, 0xa5, sizeof(result));
    unsigned char before[sizeof(result)];
    std::memcpy(before, &result, sizeof(result));
    const de_view empty{nullptr, 0}, invalid{nullptr, 1};
    const auto available = de_u64_from_u32(0);
    need(de_ntfs_boot_read(nullptr, &available, 3, 1, &result) == DE_INVALID);
    need(de_ntfs_boot_read(&empty, nullptr, 3, 1, &result) == DE_INVALID);
    need(de_ntfs_boot_read(&empty, &available, 3, 1, nullptr) == DE_INVALID);
    need(de_ntfs_boot_read(&invalid, &available, 3, 1, &result) == DE_INVALID);
    need(std::memcmp(before, &result, sizeof(result)) == 0);
    need(de_ntfs_boot_read(&empty, &available, 3, 1, &result) == DE_OK);
    need(result.issues == DE_NTFS_BOOT_TRUNCATED && !result.fields_present);
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
