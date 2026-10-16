#include "ntfs_names.h"
#include "ntfs_attributes_detail.h"

namespace disked {
namespace {
using namespace ntfs_attributes_detail;
NtfsStreamJoinRequest selection_request(const NtfsFilenameRequest &r) {
    NtfsStreamJoinRequest request;
    request.context = r.context;
    request.base_reference = r.base_reference;
    request.volume_clusters = r.volume_clusters;
    request.cluster_bytes = r.cluster_bytes;
    request.record_bytes = r.record_bytes;
    request.major = r.major;
    request.minor = r.minor;
    request.limits = r.limits;
    request.type = 0x30;
    return request;
}
class Names : public Selection {
    std::vector<NtfsFilename> names_;
    V name_facts_ = V::array();

    void collect() {
        for (const auto &selected : selected_) {
            const auto &a = *selected.attribute;
            if (a.form || a.flags || (a.resident_flags & 0xfe) || a.issues)
                stop("ntfs_names_attribute_form");
            de_ntfs_filename value{};
            checked(de_ntfs_filename_read(&a.value, request_.major, request_.minor, &value));
            if (!value.envelope_valid || value.issues)
                stop("ntfs_names_value");
            charge(512 + 2 * a.value.size + 2 * value.name.size);
            NtfsFilename owned;
            owned.reference = selected.record->input->number |
                              (std::uint64_t(selected.record->header.sequence) << 48);
            owned.parent_reference = native(value.parent_reference);
            owned.instance = a.instance;
            owned.resident_flags = a.resident_flags;
            owned.namespace_code = value.namespace_code;
            owned.name.assign(value.name.data, value.name.data + value.name.size);
            owned.value.assign(a.value.data, a.value.data + a.value.size);
            name_facts_.items.push_back(
                V::object()
                    .put("reference", exact(owned.reference))
                    .put("instance", exact(owned.instance))
                    .put("resident_flags", exact(owned.resident_flags))
                    .put("parent_reference", exact(owned.parent_reference))
                    .put("namespace", exact(owned.namespace_code))
                    .put("name_hex", V::string(hex(value.name.data, value.name.size)))
                    .put("name_sha256", V::string(digest(value.name)))
                    .put("value_bytes", exact(a.value.size))
                    .put("value_sha256", V::string(digest(a.value)))
                    .put("duplicated_information_hex",
                         V::string(hex(value.duplicated_information.data,
                                       value.duplicated_information.size)))
                    .put("suffix_bytes", exact(value.suffix.size))
                    .put("suffix_sha256", V::string(digest(value.suffix))));
            names_.push_back(std::move(owned));
        }
    }
    V report(const char *diagnostic) const {
        auto missing = V::array();
        for (const auto reference : missing_)
            missing.items.push_back(exact(reference));
        auto result =
            V::object()
                .put("schema", V::string("org.disked.ntfs-filename-collection-prototype/1"))
                .put("source_id", V::string(request_.context.source_id))
                .put("epoch", exact(request_.context.epoch))
                .put("volume_offset", exact(request_.context.volume_offset))
                .put("volume_bytes", exact(request_.context.volume_bytes))
                .put("base_reference", exact(request_.base_reference))
                .put("major", exact(request_.major))
                .put("minor", exact(request_.minor))
                .put("complete", flag(!*diagnostic))
                .put("diagnostic", V::string(diagnostic))
                .put("context_matches", flag(context_matches_))
                .put("attribute_list_present", flag(list_))
                .put("atomic_snapshot", flag(false))
                .put("current_source_authority", flag(false))
                .put("effects_authorized", flag(false))
                .put("target_membership", V::string("unverified"))
                .put("collation", V::string("unverified"))
                .put("namespace", V::string("unverified"))
                .put("required_records", std::move(missing))
                .put("records", record_facts_)
                .put("names", name_facts_)
                .put("record_count", exact(record_facts_.items.size()))
                .put("attribute_count", exact(attributes_))
                .put("list_entry_count", exact(entries_))
                .put("run_count", exact(runs_))
                .put("name_count", exact(name_facts_.items.size()));
        if (external_list_)
            result.put("external_list_bound", flag(external_list_bound_))
                .put("external_list_bytes", exact(external_list_->value.size));
        return result;
    }

  public:
    Names(const NtfsStreamJoinRequest &request, const std::vector<NtfsCapturedRecord> &inputs,
          const NtfsCapturedAttributeList *list)
        : Selection(request, inputs, list, true) {
    }
    NtfsFilenamesResult run() {
        const char *diagnostic = "";
        try {
            prepare();
            select();
        } catch (const Stop &failure) {
            diagnostic = failure.code;
        }
        // A known bad value must not be hidden behind another missing record.
        if (!*diagnostic || std::string(diagnostic) == "ntfs_join_record_missing")
            try {
                collect();
            } catch (const Stop &failure) {
                diagnostic = failure.code;
            }
        if (std::string(diagnostic) != "ntfs_join_record_missing")
            missing_.clear();
        NtfsFilenamesResult result;
        result.required_records = missing_;
        result.observation = report(diagnostic);
        json::Limits limits;
        limits.bytes = request_.limits.output_bytes;
        limits.string_bytes = 1048576;
        limits.values = 262144;
        json::dump(result.observation, limits);
        if (!*diagnostic)
            result.names.reset(new std::vector<NtfsFilename>(std::move(names_)));
        return result;
    }
};
} // namespace
NtfsFilenamesResult collect_ntfs_filenames(const NtfsFilenameRequest &request,
                                           const std::vector<NtfsCapturedRecord> &records,
                                           const NtfsCapturedAttributeList *list) {
    const auto selected = selection_request(request);
    ntfs_attributes_detail::validate(selected, records, list);
    return Names(selected, records, list).run();
}
} // namespace disked
