#include "ntfs_stream.h"
#include "ntfs_attributes_detail.h"
#include <algorithm>

namespace disked {
namespace {
using namespace ntfs_attributes_detail;
class Joiner : public Selection {
    NtfsJoinedStream stream_;
    V part_facts_ = V::array(), run_facts_ = V::array();
    void join() {
        std::sort(selected_.begin(), selected_.end(), [&](const Selected &a, const Selected &b) {
            return low(*a.attribute) < low(*b.attribute);
        });
        const auto &first = *selected_.front().attribute;
        stream_.resident = first.form == 0;
        stream_.type = request_.type;
        stream_.name = request_.name;
        for (const auto &selection : selected_)
            if ((selection.attribute->form == 0) != stream_.resident)
                stop("ntfs_join_mixed_forms");
        if (!first.form && selected_.size() != 1)
            stop("ntfs_join_resident_ambiguous");
        if (first.form && low(first))
            stop("ntfs_join_vcn_coverage");
        std::uint64_t next_vcn = 0;
        for (const auto &selection : selected_) {
            const auto &a = *selection.attribute;
            const auto &record = *selection.record;
            if ((a.form == 0) != stream_.resident)
                stop("ntfs_join_mixed_forms");
            if (a.flags || a.issues & DE_NTFS_ATTR_FEATURE)
                stop("ntfs_join_feature_unsupported");
            if (low(a) != next_vcn)
                stop("ntfs_join_vcn_coverage");
            const auto reference =
                record.input->number | (std::uint64_t(record.header.sequence) << 48);
            charge(256);
            stream_.parts.push_back(
                NtfsStreamPart{reference, low(a), a.form ? native(a.highest_vcn) : 0, a.instance});
            part_facts_.items.push_back(
                V::object()
                    .put("reference", exact(reference))
                    .put("instance", exact(a.instance))
                    .put("lowest_vcn", exact(low(a)))
                    .put("highest_vcn", a.form ? exact(native(a.highest_vcn)) : V{}));
            if (!a.form) {
                if (a.value.size)
                    stream_.value.assign(a.value.data, a.value.data + a.value.size);
                stream_.data_bytes = stream_.initialized_bytes = a.value.size;
                continue;
            }
            if (!a.ordinary_mapping)
                stop("ntfs_join_mapping");
            if (a.empty_stream && selected_.size() != 1)
                stop("ntfs_join_empty_coverage");
            if (a.sizes_applicable) {
                stream_.allocated_bytes = native(a.allocated_size);
                stream_.data_bytes = native(a.data_size);
                stream_.initialized_bytes = native(a.initialized_size);
            }
            const auto clusters = portable(request_.volume_clusters);
            de_ntfs_run_cursor cursor{};
            de_ntfs_run run{};
            checked(de_ntfs_runs_begin(&a.mapping, &a.lowest_vcn, &a.cluster_span, &clusters, 0,
                                       static_cast<unsigned>(request_.limits.runs), &cursor));
            while (de_ntfs_runs_next(&cursor, &run) == DE_OK) {
                if (run.end_marker)
                    break;
                if (runs_ == request_.limits.runs)
                    stop("ntfs_join_run_budget");
                ++runs_;
                if (!run.valid)
                    stop("ntfs_join_mapping");
                charge(192);
                stream_.runs.push_back(
                    NtfsStreamRun{native(run.vcn), native(run.length), native(run.lcn)});
                run_facts_.items.push_back(V::object()
                                               .put("vcn", exact(native(run.vcn)))
                                               .put("clusters", exact(native(run.length)))
                                               .put("lcn", exact(native(run.lcn))));
            }
            if (!cursor.terminated || cursor.issues)
                stop("ntfs_join_mapping");
            next_vcn = add(low(a), native(a.cluster_span));
        }
        if (stream_.resident)
            return;
        if (stream_.allocated_bytes != mul(next_vcn, request_.cluster_bytes))
            stop("ntfs_join_allocation");
        std::vector<std::pair<std::uint64_t, std::uint64_t>> physical;
        for (const auto &run : stream_.runs)
            physical.emplace_back(run.lcn, add(run.lcn, run.clusters));
        std::sort(physical.begin(), physical.end());
        for (std::size_t i = 1; i < physical.size(); ++i)
            if (physical[i].first < physical[i - 1].second)
                stop("ntfs_join_physical_overlap");
    }
    V report(const char *diagnostic) const {
        const bool complete = !*diagnostic;
        auto missing = V::array();
        for (const auto reference : missing_)
            missing.items.push_back(exact(reference));
        auto value =
            V::object()
                .put("schema", V::string("org.disked.ntfs-stream-join-observation-prototype/1"))
                .put("source_id", V::string(request_.context.source_id))
                .put("epoch", exact(request_.context.epoch))
                .put("volume_offset", exact(request_.context.volume_offset))
                .put("volume_bytes", exact(request_.context.volume_bytes))
                .put("base_reference", exact(request_.base_reference))
                .put("type", exact(request_.type))
                .put("name_hex", V::string(hex(request_.name.data(), request_.name.size())))
                .put("complete", flag(complete))
                .put("diagnostic", V::string(diagnostic))
                .put("context_matches", flag(context_matches_))
                .put("attribute_list_present", flag(list_))
                .put("atomic_snapshot", flag(false))
                .put("current_source_authority", flag(false))
                .put("effects_authorized", flag(false))
                .put("required_records", std::move(missing))
                .put("records", record_facts_)
                .put("parts", part_facts_)
                .put("runs", run_facts_)
                .put("record_count", exact(record_facts_.items.size()))
                .put("attribute_count", exact(attributes_))
                .put("list_entry_count", exact(entries_))
                .put("run_count", exact(runs_));
        if (complete)
            value.put("resident", flag(stream_.resident))
                .put("allocated_bytes", stream_.resident ? V{} : exact(stream_.allocated_bytes))
                .put("data_bytes", exact(stream_.data_bytes))
                .put("initialized_bytes", exact(stream_.initialized_bytes))
                .put("value_sha256",
                     stream_.resident
                         ? V::string(digest(de_view{stream_.value.data(), stream_.value.size()}))
                         : V{});
        if (external_list_)
            value.put("external_list_bound", flag(external_list_bound_))
                .put("external_list_bytes", exact(external_list_->value.size));
        return value;
    }

  public:
    Joiner(const NtfsStreamJoinRequest &request, const std::vector<NtfsCapturedRecord> &inputs,
           const NtfsCapturedAttributeList *list)
        : Selection(request, inputs, list, false) {
    }
    NtfsStreamJoinResult run() {
        const char *diagnostic = "";
        try {
            prepare();
            select();
            join();
        } catch (const Stop &failure) {
            diagnostic = failure.code;
            if (std::string(diagnostic) != "ntfs_join_record_missing")
                missing_.clear();
        }
        NtfsStreamJoinResult result;
        result.required_records = missing_;
        result.observation = report(diagnostic);
        json::Limits limits;
        limits.bytes = request_.limits.output_bytes;
        limits.string_bytes = 1048576;
        limits.values = 262144;
        json::dump(result.observation, limits);
        if (!*diagnostic)
            result.stream.reset(new NtfsJoinedStream(std::move(stream_)));
        return result;
    }
};
} // namespace
NtfsStreamJoinResult join_ntfs_stream(const NtfsStreamJoinRequest &request,
                                      const std::vector<NtfsCapturedRecord> &records,
                                      const NtfsCapturedAttributeList *list) {
    ntfs_attributes_detail::validate(request, records, list);
    return Joiner(request, records, list).run();
}
} // namespace disked
