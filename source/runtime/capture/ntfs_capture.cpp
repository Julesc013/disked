#include "ntfs_capture.h"
#include "portable/hash/sha256.h"
#include "portable/ntfs/ntfs.h"
#include <algorithm>
#include <deque>
#include <limits>
#include <vector>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
struct Stop {
    const char *code;
};
[[noreturn]] void stop(const char *code) {
    throw Stop{code};
}
void checked(int code) {
    if (code)
        throw std::logic_error("ntfs_capture_internal");
}
de_u64 portable(std::uint64_t n) {
    const auto text = std::to_string(n);
    de_u64 value{};
    checked(de_u64_parse(text.data(), text.size(), &value));
    return value;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    checked(de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    if (b > std::numeric_limits<std::uint64_t>::max() - a)
        stop("ntfs_extent_overflow");
    return a + b;
}
std::uint64_t mul(std::uint64_t a, std::uint64_t b) {
    if (a && b > std::numeric_limits<std::uint64_t>::max() / a)
        stop("ntfs_extent_overflow");
    return a * b;
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V flag(bool n) {
    return V::boolean_value(n);
}
std::string hex(const unsigned char *p, std::size_t n) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(n * 2);
    for (std::size_t i = 0; i < n; ++i) {
        out += digits[p[i] >> 4];
        out += digits[p[i] & 15];
    }
    return out;
}
std::string digest(const unsigned char *p, std::size_t n) {
    const unsigned char empty = 0;
    unsigned char result[32];
    sha256(n ? p : &empty, n, result);
    return "sha256:" + hex(result, sizeof(result));
}
json::Limits json_limits(std::size_t bytes = 1048576) {
    json::Limits limits;
    limits.bytes = bytes;
    limits.string_bytes = 1048576;
    limits.values = 262144;
    return limits;
}
bool overlap(std::uint64_t a, std::uint64_t b, std::uint64_t c, std::uint64_t d) {
    return a < d && c < b;
}
struct Region {
    std::uint64_t start;
    Bytes bytes;
};
struct Mapping {
    std::uint64_t vcn, count, lcn;
    bool sparse;
};
struct Attribute {
    de_ntfs_attribute value{};
    std::vector<Mapping> runs;
    bool mapped = false;
};
struct Record {
    de_ntfs_record header{};
    Bytes logical;
    std::vector<Attribute> attributes;
    V report = V::object().put("observed", flag(false));
    bool good = false;
    bool mapping_error = false;
};
class Observer {
    // Own both controls before the first callback; callbacks cannot widen scope.
    const NtfsCaptureRequest request_;
    const RegionReader reader_;
    de_block_space source_{};
    de_ntfs_boot boot_{};
    std::deque<Region> regions_;
    V region_facts_ = V::array(), boot_facts_ = V::object(), mft_facts_ = V::object();
    V volume_facts_ = V::object();
    Record primary_, mirror_, volume_;
    std::size_t reads_ = 0, bytes_ = 0, retained_ = 0, attributes_ = 0, runs_ = 0;
    std::size_t output_ = 8192, reread_start_ = 0;
    bool rereading_ = false, reread_equal_ = false, complete_ = false;
    bool mirror_equal_ = false, version_matches_ = false;
    const char *diagnostic_ = "";

    void charge(std::size_t n) {
        if (n > request_.limits.output_bytes - output_)
            stop("ntfs_output_budget");
        output_ += n;
    }
    void charge(const V &item) {
        charge(json::dump(item, json_limits()).size() + 2);
    }
    de_view fetch(std::uint64_t absolute, std::size_t size) {
        if (!size || absolute < request_.volume_offset ||
            absolute - request_.volume_offset > request_.volume_bytes ||
            size > request_.volume_bytes - (absolute - request_.volume_offset))
            stop("ntfs_read_bounds");
        if (reads_ == request_.limits.read_requests || size > request_.limits.read_bytes - bytes_)
            stop("ntfs_read_budget");
        const auto start = portable(absolute), length = portable(size);
        de_block_extent block{};
        de_byte_extent extent{};
        checked(de_extent_make(&source_, &start, &length, &block));
        checked(de_extent_to_bytes(&block, &extent));
        ++reads_;
        bytes_ += size;
        de_view borrowed{};
        try {
            borrowed = reader_(extent);
        } catch (...) {
            stop("ntfs_reader_failure");
        }
        if (!borrowed.data || borrowed.size != size)
            stop("ntfs_read_length");
        return borrowed;
    }
    const Bytes &read(std::uint64_t relative, std::size_t size) {
        if (size > request_.limits.retained_bytes - retained_)
            stop("ntfs_retained_budget");
        charge(256); // Exact region metadata is smaller, even at full u64 widths.
        const auto absolute = add(request_.volume_offset, relative);
        const auto raw = fetch(absolute, size);
        regions_.push_back(Region{absolute, Bytes(raw.data, raw.data + size)});
        retained_ += size;
        const auto &current = regions_.back();
        region_facts_.items.push_back(
            V::object()
                .put("offset", exact(absolute))
                .put("bytes", exact(size))
                .put("sha256", V::string(digest(current.bytes.data(), size))));
        for (auto it = regions_.begin(); &*it != &current; ++it) {
            const auto first = std::max(absolute, it->start);
            const auto last = std::min(add(absolute, size), add(it->start, it->bytes.size()));
            if (first < last &&
                !std::equal(current.bytes.begin() + static_cast<std::size_t>(first - absolute),
                            current.bytes.begin() + static_cast<std::size_t>(last - absolute),
                            it->bytes.begin() + static_cast<std::size_t>(first - it->start)))
                stop("ntfs_source_changed");
        }
        return current.bytes;
    }
    V attribute_value(const de_ntfs_attribute &a) {
        auto result = V::object()
                          .put("present", flag(a.present != 0))
                          .put("type", exact(a.type))
                          .put("length", exact(a.record_length))
                          .put("form", exact(a.form))
                          .put("flags", exact(a.flags))
                          .put("instance", exact(a.instance))
                          .put("issues", exact(a.issues))
                          .put("envelope_valid", flag(a.envelope_valid != 0))
                          .put("name_hex", V::string(hex(a.name.data, a.name.size)))
                          .put("runs", V::array())
                          .put("runs_complete", flag(false));
        if (a.variant_fields && a.form == 0) {
            result.put("value_bytes", exact(a.value.size))
                .put("value_sha256", V::string(digest(a.value.data, a.value.size)));
        } else if (a.variant_fields && a.form == 1) {
            result.put("lowest_vcn", exact(native(a.lowest_vcn)))
                .put("highest_vcn", exact(native(a.highest_vcn)))
                .put("allocated_bytes", exact(native(a.allocated_size)))
                .put("data_bytes", exact(native(a.data_size)))
                .put("initialized_bytes", exact(native(a.initialized_size)))
                .put("sizes_applicable", flag(a.sizes_applicable != 0))
                .put("mapping_bytes", exact(a.mapping.size))
                .put("mapping_sha256", V::string(digest(a.mapping.data, a.mapping.size)));
        }
        return result;
    }
    void mappings(Attribute &a, V &item) {
        if (!a.value.ordinary_mapping)
            return;
        de_ntfs_run_cursor cursor{};
        checked(de_ntfs_runs_begin(&a.value.mapping, &a.value.lowest_vcn, &a.value.cluster_span,
                                   &boot_.clusters, (a.value.flags & 0x8000) ? 1 : 0,
                                   static_cast<unsigned>(request_.limits.runs), &cursor));
        de_ntfs_run run{};
        while (de_ntfs_runs_next(&cursor, &run) == DE_OK) {
            if (run.end_marker)
                break;
            if (runs_ == request_.limits.runs)
                stop("ntfs_run_budget");
            ++runs_;
            auto fact = V::object()
                            .put("valid", flag(run.valid != 0))
                            .put("issues", exact(run.issues))
                            .put("vcn", exact(native(run.vcn)))
                            .put("clusters", exact(native(run.length)))
                            .put("sparse", flag(run.sparse != 0))
                            .put("lcn", exact(native(run.lcn)));
            charge(fact);
            item.fields.at("runs").items.push_back(std::move(fact));
            if (run.valid)
                a.runs.push_back(
                    Mapping{native(run.vcn), native(run.length), native(run.lcn), run.sparse != 0});
        }
        a.mapped = cursor.terminated && !cursor.issues;
        item.put("runs_complete", flag(a.mapped)).put("run_issues", exact(cursor.issues));
    }
    void parse(Record &record, const Bytes &raw, unsigned expected_number) {
        const de_view original{raw.data(), raw.size()};
        checked(de_ntfs_record_read(&original, request_.major, request_.minor, &record.header));
        const auto &h = record.header;
        record.report.put("observed", flag(true))
            .put("raw_sha256", V::string(digest(raw.data(), raw.size())))
            .put("envelope_valid", flag(h.envelope_valid != 0))
            .put("issues", exact(h.issues))
            .put("used_bytes", exact(h.used_bytes))
            .put("sequence", exact(h.sequence))
            .put("log_sequence", exact(native(h.log_sequence)))
            .put("base_reference", exact(native(h.base_reference)))
            .put("flags", exact(h.flags))
            .put("attributes", V::array())
            .put("attributes_complete", flag(false));
        if (!h.envelope_valid)
            return;
        const bool number_known = h.usa_offset >= 48;
        de_u64 number{};
        if (number_known)
            checked(de_view_read_uint(&original, 44, 4, DE_LITTLE_ENDIAN, &number));
        const bool number_matches = !number_known || native(number) == expected_number;
        record.report.put("record_number_known", flag(number_known))
            .put("record_number", exact(native(number)))
            .put("record_number_matches", flag(number_matches));
        record.logical.resize(raw.size());
        const de_buffer restored{record.logical.data(), record.logical.size()};
        de_ntfs_attr_cursor cursor{};
        checked(de_ntfs_attributes_begin(&original, request_.major, request_.minor, &restored,
                                         static_cast<unsigned>(request_.limits.attributes),
                                         &cursor));
        de_ntfs_attribute value{};
        while (de_ntfs_attributes_next(&cursor, &value) == DE_OK) {
            if (value.end_marker)
                break;
            if (attributes_ == request_.limits.attributes)
                stop("ntfs_attribute_budget");
            ++attributes_;
            auto item = attribute_value(value);
            charge(item);
            charge(64); // Mapping completion fields can grow after the header is retained.
            record.report.fields.at("attributes").items.push_back(std::move(item));
            record.attributes.push_back(Attribute{});
            auto &a = record.attributes.back();
            a.value = value;
            mappings(a, record.report.fields.at("attributes").items.back());
            if (a.value.ordinary_mapping && !a.mapped)
                record.mapping_error = true;
        }
        const bool complete =
            cursor.terminated && !(cursor.issues & ~(DE_NTFS_ATTR_TYPE | DE_NTFS_ATTR_FEATURE));
        record.report.put("attributes_complete", flag(complete))
            .put("attribute_issues", exact(cursor.issues))
            .put("mappings_valid", flag(!record.mapping_error));
        record.good = complete && !record.mapping_error && h.flags == 1 &&
                      !native(h.base_reference) && number_matches;
    }
    bool mirror_equal() const {
        if (!primary_.good || !mirror_.good)
            return false;
        const auto &a = primary_.header, &b = mirror_.header;
        if (a.used_bytes != b.used_bytes || a.usa_offset != b.usa_offset ||
            a.usa_count != b.usa_count)
            return false;
        const auto end = a.usa_offset + static_cast<std::size_t>(a.usa_count) * 2;
        for (std::size_t i = 0; i < a.used_bytes; ++i)
            if ((i < a.usa_offset || i >= end) && primary_.logical[i] != mirror_.logical[i])
                return false;
        return true;
    }
    std::vector<std::pair<std::uint64_t, std::size_t>>
    pieces(const Attribute &a, std::uint64_t start, std::size_t length) {
        std::vector<std::pair<std::uint64_t, std::size_t>> out;
        auto next = start;
        const auto end = add(start, length);
        for (const auto &run : a.runs) {
            const auto first = mul(run.vcn, boot_.cluster_bytes);
            const auto last = add(first, mul(run.count, boot_.cluster_bytes));
            if (next < first)
                break;
            if (next >= last)
                continue;
            const auto count = std::min(end - next, last - next);
            if (run.sparse)
                stop("ntfs_mft_sparse");
            out.emplace_back(add(mul(run.lcn, boot_.cluster_bytes), next - first),
                             static_cast<std::size_t>(count));
            next += count;
            if (next == end)
                break;
        }
        if (next != end)
            stop("ntfs_mft_coverage");
        return out;
    }
    const Attribute &mft() {
        if (primary_.mapping_error)
            stop("ntfs_primary_mapping");
        if (!primary_.good)
            stop("ntfs_primary_record");
        const Attribute *selected = nullptr;
        for (const auto &a : primary_.attributes) {
            if (a.value.type == 0x20)
                stop("ntfs_mft_attribute_list_unsupported");
            if (a.value.type != 0x80 || a.value.name_length)
                continue;
            if (selected)
                stop("ntfs_mft_data_ambiguous");
            selected = &a;
        }
        if (!selected || !selected->mapped || selected->value.flags ||
            !selected->value.sizes_applicable || selected->value.empty_stream)
            stop("ntfs_mft_data_unsupported");
        const auto &a = *selected;
        const auto allocated = native(a.value.allocated_size), data = native(a.value.data_size),
                   initialized = native(a.value.initialized_size);
        if (allocated != mul(native(a.value.cluster_span), boot_.cluster_bytes) ||
            data % boot_.record_bytes || initialized % boot_.record_bytes ||
            initialized < mul(4, boot_.record_bytes))
            stop("ntfs_mft_sizes");
        std::vector<std::pair<std::uint64_t, std::uint64_t>> physical;
        for (const auto &run : a.runs) {
            const auto begin = mul(run.lcn, boot_.cluster_bytes),
                       end = add(begin, mul(run.count, boot_.cluster_bytes));
            if (run.sparse || overlap(begin, end, 0, boot_.bytes_per_sector) ||
                overlap(begin, end, native(boot_.mirror0_offset),
                        add(native(boot_.mirror0_offset), boot_.record_bytes)))
                stop("ntfs_mft_physical_alias");
            physical.emplace_back(begin, end);
        }
        std::sort(physical.begin(), physical.end());
        for (std::size_t i = 1; i < physical.size(); ++i)
            if (physical[i].first < physical[i - 1].second)
                stop("ntfs_mft_physical_alias");
        auto expected = native(boot_.mft0_offset);
        for (const auto &part : pieces(a, 0, boot_.record_bytes)) {
            if (part.first != expected)
                stop("ntfs_mft_seed_mapping");
            expected = add(expected, part.second);
        }
        mft_facts_.put("mapping_valid", flag(true))
            .put("allocated_bytes", exact(allocated))
            .put("data_bytes", exact(data))
            .put("initialized_bytes", exact(initialized))
            .put("runs", exact(a.runs.size()));
        return a;
    }
    void collect() {
        const auto &prefix = read(0, 512);
        const auto sector =
            static_cast<unsigned>(prefix[11]) + static_cast<unsigned>(prefix[12]) * 256;
        const Bytes *boot_bytes = &prefix;
        if (sector == 1024 || sector == 2048 || sector == 4096)
            boot_bytes = &read(0, sector);
        const auto available = portable(request_.volume_bytes);
        const de_view raw{boot_bytes->data(), boot_bytes->size()};
        checked(de_ntfs_boot_read(&raw, &available, request_.major, request_.minor, &boot_));
        boot_facts_.put("issues", exact(boot_.issues))
            .put("bootstrap_usable", flag(boot_.bootstrap_usable != 0))
            .put("sector_bytes", exact(boot_.bytes_per_sector))
            .put("cluster_bytes", exact(boot_.cluster_bytes))
            .put("record_bytes", exact(boot_.record_bytes))
            .put("data_bytes", exact(native(boot_.data_bytes)))
            .put("media_span_bytes", exact(native(boot_.media_span_bytes)))
            .put("clusters", exact(native(boot_.clusters)))
            .put("mft0_offset", exact(native(boot_.mft0_offset)))
            .put("mirror0_offset", exact(native(boot_.mirror0_offset)));
        if (!boot_.bootstrap_usable)
            stop("ntfs_boot_geometry");
        parse(primary_,
              read(native(boot_.mft0_offset), static_cast<std::size_t>(boot_.record_bytes)), 0);
        parse(mirror_,
              read(native(boot_.mirror0_offset), static_cast<std::size_t>(boot_.record_bytes)), 0);
        mirror_equal_ = mirror_equal();
        const auto &data = mft();
        Bytes assembled;
        assembled.reserve(static_cast<std::size_t>(boot_.record_bytes));
        const auto start = mul(3, boot_.record_bytes);
        for (const auto &part : pieces(data, start, static_cast<std::size_t>(boot_.record_bytes))) {
            const auto &bytes = read(part.first, part.second);
            assembled.insert(assembled.end(), bytes.begin(), bytes.end());
        }
        parse(volume_, assembled, 3);
        if (volume_.mapping_error)
            stop("ntfs_volume_mapping");
        if (!volume_.good)
            stop("ntfs_volume_record");
        const Attribute *info = nullptr;
        for (const auto &a : volume_.attributes) {
            if (a.value.type == 0x20)
                stop("ntfs_volume_attribute_list_unsupported");
            if (a.value.type != 0x70)
                continue;
            if (info)
                stop("ntfs_volume_information_ambiguous");
            info = &a;
        }
        if (!info || info->value.form || info->value.name_length || info->value.flags ||
            !info->value.envelope_valid || info->value.value.size < 12)
            stop("ntfs_volume_information");
        const auto &value = info->value.value;
        version_matches_ = value.data[8] == request_.major && value.data[9] == request_.minor;
        volume_facts_.put("major", exact(value.data[8]))
            .put("minor", exact(value.data[9]))
            .put("flags", exact(static_cast<unsigned>(value.data[10]) +
                                static_cast<unsigned>(value.data[11]) * 256))
            .put("value_bytes", exact(value.size))
            .put("sha256", V::string(digest(value.data, value.size)))
            .put("profile_matches", flag(version_matches_));
        rereading_ = true;
        reread_start_ = reads_;
        for (const auto &region : regions_) {
            const auto again = fetch(region.start, region.bytes.size());
            if (!std::equal(region.bytes.begin(), region.bytes.end(), again.data))
                stop("ntfs_source_changed");
        }
        reread_equal_ = true;
        complete_ = true;
        if (mirror_.mapping_error)
            diagnostic_ = "ntfs_mirror_mapping";
        else if (!mirror_.good)
            diagnostic_ = "ntfs_mirror_record";
        else if (!mirror_equal_)
            diagnostic_ = "ntfs_mirror_disagreement";
        else if (!version_matches_)
            diagnostic_ = "ntfs_volume_version";
    }
    V report() const {
        return V::object()
            .put("schema", V::string("org.disked.ntfs-bootstrap-observation-prototype/1"))
            .put("source_id", V::string(request_.source_id))
            .put("epoch", exact(request_.epoch))
            .put("volume_offset", exact(request_.volume_offset))
            .put("volume_bytes", exact(request_.volume_bytes))
            .put("requested_major", exact(request_.major))
            .put("requested_minor", exact(request_.minor))
            .put("complete", flag(complete_))
            .put("applicable", flag(complete_ && !*diagnostic_))
            .put("diagnostic", V::string(diagnostic_))
            .put("reread_equal", flag(reread_equal_))
            .put("atomic_snapshot", flag(false))
            .put("current_source_authority", flag(false))
            .put("effects_authorized", flag(false))
            .put("boot", boot_facts_)
            .put("primary", primary_.report)
            .put("mirror", mirror_.report)
            .put("mirror_used_payload_equal", flag(mirror_equal_))
            .put("mft", mft_facts_)
            .put("volume_record", volume_.report)
            .put("volume_information", volume_facts_)
            .put("regions", region_facts_)
            .put("read_requests", exact(reads_))
            .put("read_bytes", exact(bytes_))
            .put("retained_bytes", exact(retained_))
            .put("attributes", exact(attributes_))
            .put("runs", exact(runs_))
            .put("reread_requests", exact(rereading_ ? reads_ - reread_start_ : 0));
    }

  public:
    Observer(const NtfsCaptureRequest &request, const RegionReader &reader)
        : request_(request), reader_(reader) {
        validate_ntfs_capture_request(request_);
        if (!reader_)
            throw std::invalid_argument("ntfs_capture_reader");
        const auto size = portable(request_.source_bytes);
        checked(de_space_from_bytes(request_.source_id.data(), request_.source_id.size(), &size, 1,
                                    &source_));
    }
    V run() {
        try {
            collect();
        } catch (const Stop &failure) {
            diagnostic_ = failure.code;
        }
        auto value = report();
        // The fixed reserve plus charged variable items bound even failure reports.
        json::dump(value, json_limits(request_.limits.output_bytes));
        return value;
    }
};
} // namespace
void validate_ntfs_capture_request(const NtfsCaptureRequest &r) {
    if (!r.epoch || !r.source_bytes || r.volume_bytes < 512 || r.source_id.empty() ||
        r.source_id.size() > 128 || r.source_id.find('\0') != std::string::npos ||
        !json::valid_utf8(r.source_id) || r.major != 3 || r.minor > 1)
        throw std::invalid_argument("ntfs_capture_inputs");
    if (r.volume_offset > r.source_bytes || r.volume_bytes > r.source_bytes - r.volume_offset)
        throw std::invalid_argument("ntfs_capture_window");
    const auto &l = r.limits;
    if (!l.read_requests || l.read_requests > 512 || !l.read_bytes || l.read_bytes > 2097152 ||
        !l.retained_bytes || l.retained_bytes > 524288 || !l.attributes || l.attributes > 4096 ||
        !l.runs || l.runs > 4096 || l.output_bytes < 16384 || l.output_bytes > 1048576)
        throw std::invalid_argument("ntfs_capture_limits");
}
V observe_ntfs_bootstrap(const NtfsCaptureRequest &request, const RegionReader &reader) {
    return Observer(request, reader).run();
}
} // namespace disked
