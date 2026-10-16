#include "ntfs_attributes_detail.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <set>
#include <stdexcept>

namespace disked {
namespace ntfs_attributes_detail {
using V = json::Value;
constexpr std::uint64_t record_mask = (std::uint64_t(1) << 48) - 1;
[[noreturn]] void stop(const char *code) {
    throw Stop{code};
}
void checked(int code) {
    if (code)
        throw std::logic_error("ntfs_join_internal");
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    checked(de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
de_u64 portable(std::uint64_t n) {
    const auto text = std::to_string(n);
    de_u64 value{};
    checked(de_u64_parse(text.data(), text.size(), &value));
    return value;
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    if (b > UINT64_MAX - a)
        stop("ntfs_join_overflow");
    return a + b;
}
std::uint64_t mul(std::uint64_t a, std::uint64_t b) {
    if (a && b > UINT64_MAX / a)
        stop("ntfs_join_overflow");
    return a * b;
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V flag(bool n) {
    return V::boolean_value(n);
}
std::string hex(const unsigned char *data, std::size_t bytes) {
    const char digits[] = "0123456789abcdef";
    std::string text;
    text.reserve(bytes * 2);
    for (std::size_t i = 0; i < bytes; ++i) {
        text += digits[data[i] >> 4];
        text += digits[data[i] & 15];
    }
    return text;
}
std::string digest(const de_view &view) {
    const unsigned char empty = 0;
    unsigned char result[32];
    sha256(view.size ? view.data : &empty, view.size, result);
    return "sha256:" + hex(result, 32);
}
bool same(const de_view &view, const std::vector<unsigned char> &name) {
    return view.size == name.size() &&
           (!view.size || std::equal(name.begin(), name.end(), view.data));
}
bool same(const NtfsStreamContext &a, const NtfsStreamContext &b) {
    return a.source_id == b.source_id && a.epoch == b.epoch && a.volume_offset == b.volume_offset &&
           a.volume_bytes == b.volume_bytes;
}
void validate(const NtfsStreamJoinRequest &r, const std::vector<NtfsCapturedRecord> &records,
              const NtfsCapturedAttributeList *list) {
    const auto &c = r.context;
    const auto &l = r.limits;
    if (c.source_id.empty() || c.source_id.size() > 128 ||
        c.source_id.find('\0') != c.source_id.npos || !json::valid_utf8(c.source_id) || !c.epoch ||
        !c.volume_bytes || c.volume_offset > UINT64_MAX - c.volume_bytes || r.major != 3 ||
        r.minor > 1 || !r.volume_clusters || r.cluster_bytes < 512 || r.cluster_bytes > 2097152 ||
        (r.cluster_bytes & (r.cluster_bytes - 1)) ||
        r.volume_clusters > c.volume_bytes / r.cluster_bytes || r.record_bytes < 512 ||
        r.record_bytes > DE_NTFS_MAX_RECORD || r.record_bytes % 512 || !(r.base_reference >> 48) ||
        r.type < 16 || r.type > 256 || r.type % 16 || r.name.size() > 510 || r.name.size() % 2)
        throw std::invalid_argument("ntfs_join_inputs");
    if (!l.records || l.records > 256 || !l.record_bytes || l.record_bytes > 1048576 ||
        !l.attributes || l.attributes > 4096 || !l.list_entries || l.list_entries > 4096 ||
        !l.runs || l.runs > 4096 || l.output_bytes < 16384 || l.output_bytes > 1048576 ||
        !l.list_bytes || l.list_bytes > 262144)
        throw std::invalid_argument("ntfs_join_limits");
    if (list && !list->value.data && list->value.size)
        throw std::invalid_argument("ntfs_join_list_inputs");
    // Do not traverse an unbounded supplied array merely to reject its count.
    if (records.size() > l.records)
        return;
    for (const auto &record : records)
        if (record.number > record_mask || (!record.bytes.data && record.bytes.size) ||
            record.bytes.size > DE_NTFS_MAX_RECORD)
            throw std::invalid_argument("ntfs_join_record_inputs");
}
Selection::Selection(const NtfsStreamJoinRequest &request,
                     const std::vector<NtfsCapturedRecord> &inputs,
                     const NtfsCapturedAttributeList *list, bool filenames)
    : request_(request), inputs_(inputs), external_list_(list), filenames_(filenames) {
}
void Selection::charge(std::size_t bytes) {
    if (bytes > request_.limits.output_bytes - charged_)
        stop("ntfs_join_output_budget");
    charged_ += bytes;
}
void Selection::prepare() {
    if (inputs_.size() > request_.limits.records)
        stop("ntfs_join_record_budget");
    std::size_t bytes = 0;
    for (const auto &input : inputs_) {
        if (!same(request_.context, input.context))
            stop("ntfs_join_context");
        if (input.bytes.size > request_.limits.record_bytes - bytes)
            stop("ntfs_join_byte_budget");
        bytes += input.bytes.size;
        if (!available_.emplace(input.number, &input).second)
            stop("ntfs_join_record_ambiguous");
    }
    context_matches_ = true;
}
Record &Selection::load(std::uint64_t reference) {
    const auto ordinal = reference & record_mask;
    auto found = loaded_.find(ordinal);
    if (found != loaded_.end()) {
        if (found->second->header.sequence != (reference >> 48))
            stop("ntfs_join_sequence");
        return *found->second;
    }
    const auto input = available_.find(ordinal);
    if (input == available_.end()) {
        charge(64);
        missing_.push_back(reference);
        stop("ntfs_join_record_missing");
    }
    const auto &raw = input->second->bytes;
    if (raw.size != request_.record_bytes)
        stop("ntfs_join_record_size");
    std::unique_ptr<Record> owned(new Record{});
    auto &record = *owned;
    record.input = input->second;
    checked(de_ntfs_record_read(&raw, request_.major, request_.minor, &record.header));
    const auto &h = record.header;
    charge(256);
    record_facts_.items.push_back(V::object()
                                      .put("number", exact(ordinal))
                                      .put("sequence", exact(h.sequence))
                                      .put("base_reference", exact(native(h.base_reference)))
                                      .put("issues", exact(h.issues))
                                      .put("sha256", V::string(digest(raw))));
    if (!h.envelope_valid)
        stop("ntfs_join_record_envelope");
    if (h.flags != 1 && h.flags != 3)
        stop("ntfs_join_record_flags");
    if (!h.sequence || h.sequence != (reference >> 48))
        stop("ntfs_join_sequence");
    if (native(h.base_reference) !=
        (ordinal == (request_.base_reference & record_mask) ? 0 : request_.base_reference))
        stop("ntfs_join_base_reference");
    if (h.usa_offset >= 48) {
        de_u64 number{};
        checked(de_view_read_uint(&raw, 44, 4, DE_LITTLE_ENDIAN, &number));
        if (native(number) != ordinal)
            stop("ntfs_join_record_number");
    }
    record.logical.resize(raw.size);
    const de_buffer restored{record.logical.data(), record.logical.size()};
    de_ntfs_attr_cursor cursor{};
    checked(de_ntfs_attributes_begin(&raw, request_.major, request_.minor, &restored,
                                     static_cast<unsigned>(request_.limits.attributes), &cursor));
    de_ntfs_attribute attribute{};
    std::set<unsigned> instances;
    while (de_ntfs_attributes_next(&cursor, &attribute) == DE_OK) {
        if (attribute.end_marker)
            break;
        if (attributes_ == request_.limits.attributes)
            stop("ntfs_join_attribute_budget");
        ++attributes_;
        if (!attribute.present || !attribute.envelope_valid)
            stop("ntfs_join_attributes");
        if (!instances.insert(attribute.instance).second)
            stop("ntfs_join_instance_ambiguous");
        if (filenames_ && attribute.type == 0x30 && attribute.name_length)
            stop("ntfs_names_attribute_name");
        record.attributes.push_back(attribute);
    }
    if (!cursor.terminated || cursor.issues & ~(DE_NTFS_ATTR_TYPE | DE_NTFS_ATTR_FEATURE))
        stop("ntfs_join_attributes");
    loaded_.emplace(ordinal, std::move(owned));
    return record;
}
bool Selection::matches(const de_ntfs_attribute &a) const {
    return a.type == request_.type && same(a.name, request_.name);
}
std::uint64_t Selection::low(const de_ntfs_attribute &a) const {
    return a.form ? native(a.lowest_vcn) : 0;
}
de_view Selection::list_value(const Record &base, const de_ntfs_attribute &list) {
    if (list.flags || list.name_length || list.issues & DE_NTFS_ATTR_FEATURE)
        stop("ntfs_join_list_unsupported");
    if (!list.form) {
        if (external_list_)
            stop("ntfs_join_unexpected_list_capture");
        return list.value;
    }
    if (!external_list_)
        stop("ntfs_join_nonresident_list_unsupported");
    const auto &capture = *external_list_;
    if (!same(capture.context, request_.context) ||
        capture.base_reference != request_.base_reference || capture.instance != list.instance ||
        capture.base_record_sha256 != digest(base.input->bytes))
        stop("ntfs_join_list_binding");
    if (capture.value.size > request_.limits.list_bytes)
        stop("ntfs_join_list_byte_budget");
    if (!list.ordinary_mapping || !list.sizes_applicable || list.empty_stream ||
        !native(list.data_size) || native(list.initialized_size) != native(list.data_size) ||
        capture.value.size != native(list.data_size) ||
        native(list.allocated_size) != mul(native(list.cluster_span), request_.cluster_bytes))
        stop("ntfs_join_list_sizes");
    const auto clusters = portable(request_.volume_clusters);
    de_ntfs_run_cursor cursor{};
    de_ntfs_run run{};
    checked(de_ntfs_runs_begin(&list.mapping, &list.lowest_vcn, &list.cluster_span, &clusters, 0,
                               static_cast<unsigned>(request_.limits.runs), &cursor));
    std::vector<std::pair<std::uint64_t, std::uint64_t>> physical;
    while (de_ntfs_runs_next(&cursor, &run) == DE_OK) {
        if (run.end_marker)
            break;
        if (runs_ == request_.limits.runs)
            stop("ntfs_join_run_budget");
        ++runs_;
        if (!run.valid)
            stop("ntfs_join_list_mapping");
        charge(192);
        physical.emplace_back(native(run.lcn), native(run.lcn_end));
    }
    if (!cursor.terminated || cursor.issues)
        stop("ntfs_join_list_mapping");
    std::sort(physical.begin(), physical.end());
    for (std::size_t i = 1; i < physical.size(); ++i)
        if (physical[i].first < physical[i - 1].second)
            stop("ntfs_join_list_physical_overlap");
    external_list_bound_ = true;
    return capture.value;
}
void Selection::select() {
    if (request_.type == 0x20)
        stop("ntfs_join_list_query_unsupported");
    auto &base = load(request_.base_reference);
    const de_ntfs_attribute *list = nullptr;
    for (const auto &a : base.attributes)
        if (a.type == 0x20) {
            if (list)
                stop("ntfs_join_list_ambiguous");
            list = &a;
        }
    if (!list) {
        if (external_list_)
            stop("ntfs_join_unexpected_list_capture");
        for (const auto &a : base.attributes)
            if (matches(a))
                selected_.push_back(Selected{&base, &a});
        if (selected_.empty() && !filenames_)
            stop("ntfs_join_attribute_missing");
        if (selected_.size() != 1 && !filenames_)
            stop("ntfs_join_attribute_ambiguous");
        return;
    }
    list_ = true;
    const auto value = list_value(base, *list);
    if (!value.size)
        stop("ntfs_join_list_empty");
    de_ntfs_attr_list_cursor cursor{};
    de_ntfs_attr_list_entry entry{};
    checked(de_ntfs_attr_list_begin(&value, request_.major, request_.minor,
                                    static_cast<unsigned>(request_.limits.list_entries), &cursor));
    std::set<std::pair<std::uint64_t, unsigned>> keys;
    struct Entry {
        std::uint64_t reference, lowest_vcn;
        unsigned instance;
    };
    std::vector<Entry> plan;
    std::map<std::uint64_t, unsigned> generations;
    while (de_ntfs_attr_list_next(&cursor, &entry) == DE_OK) {
        if (entry.issues & DE_NTFS_LIST_BUDGET)
            stop("ntfs_join_list_budget");
        if (entry.present)
            ++entries_;
        if (!entry.present || !entry.envelope_valid || !entry.sequence)
            stop("ntfs_join_list");
        if (filenames_ && entry.type == 0x30 && entry.name_length)
            stop("ntfs_names_attribute_name");
        if (entry.type != request_.type || !same(entry.name, request_.name))
            continue;
        const auto ordinal = native(entry.record_number),
                   reference = native(entry.segment_reference);
        const auto generation = generations.emplace(ordinal, entry.sequence);
        if (!generation.second && generation.first->second != entry.sequence)
            stop("ntfs_join_reference_ambiguous");
        if (!keys.emplace(ordinal, entry.attribute_id).second)
            stop("ntfs_join_list_duplicate");
        plan.push_back(Entry{reference, native(entry.lowest_vcn), entry.attribute_id});
    }
    if (!cursor.terminated || cursor.issues & ~DE_NTFS_LIST_TYPE)
        stop("ntfs_join_list");
    if (plan.empty() && !filenames_)
        stop("ntfs_join_attribute_missing");
    std::set<std::uint64_t> missing;
    for (const auto &dependency : plan) {
        if (!available_.count(dependency.reference & record_mask)) {
            if (missing.insert(dependency.reference).second) {
                charge(64);
                missing_.push_back(dependency.reference);
            }
            continue;
        }
        auto &record = load(dependency.reference);
        const de_ntfs_attribute *attribute = nullptr;
        for (const auto &a : record.attributes)
            if (a.instance == dependency.instance)
                attribute = &a;
        if (!attribute)
            stop("ntfs_join_instance_missing");
        if (!matches(*attribute) || low(*attribute) != dependency.lowest_vcn)
            stop("ntfs_join_entry_mismatch");
        selected_.push_back(Selected{&record, attribute});
    }
    for (const auto &record : loaded_)
        for (const auto &a : record.second->attributes)
            if (matches(a) && !keys.count({record.first, a.instance}))
                stop("ntfs_join_unlisted_attribute");
    if (!missing_.empty())
        stop("ntfs_join_record_missing");
}
} // namespace ntfs_attributes_detail
} // namespace disked
