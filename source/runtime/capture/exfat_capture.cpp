#include "exfat_capture.h"
#include "portable/exfat/exfat.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <array>
#include <set>
#include <vector>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
struct Stop {
    std::string code;
};
[[noreturn]] void stop(const char *code) {
    throw Stop{code};
}
void checked(int code) {
    if (code)
        stop("exfat_internal");
}
de_u64 portable(std::uint64_t n) {
    de_u64 out{};
    const auto text = std::to_string(n);
    checked(de_u64_parse(text.data(), text.size(), &out));
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    checked(de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    const auto left = portable(a), right = portable(b);
    de_u64 out{};
    if (de_u64_add(&left, &right, &out))
        stop("exfat_extent_overflow");
    return native(out);
}
std::uint64_t mul(std::uint64_t a, std::uint64_t b) {
    const auto left = portable(a), right = portable(b);
    de_u64 out{};
    if (de_u64_mul(&left, &right, &out))
        stop("exfat_extent_overflow");
    return native(out);
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const unsigned char *p, std::size_t n) {
    const char alphabet[] = "0123456789abcdef";
    std::string result;
    result.reserve(n * 2);
    for (std::size_t i = 0; i < n; ++i) {
        result += alphabet[p[i] >> 4];
        result += alphabet[p[i] & 15];
    }
    return result;
}
std::string digest(const Bytes &bytes) {
    unsigned char value[32];
    sha256(bytes.data(), bytes.size(), value);
    return "sha256:" + hex(value, sizeof(value));
}
json::Limits output_limits() {
    json::Limits limits;
    limits.bytes = 4194304;
    limits.string_bytes = 2097152;
    limits.values = 262144;
    limits.depth = 32;
    return limits;
}
struct Region {
    std::uint64_t start;
    Bytes bytes;
};
struct Record {
    std::uint64_t start;
    std::array<unsigned char, 32> bytes;
};
struct Chain {
    std::vector<std::uint32_t> clusters;
    V cells = V::array();
    bool complete = false;
};
V chain_value(const Chain &chain) {
    auto clusters = V::array();
    for (auto n : chain.clusters)
        clusters.items.push_back(exact(n));
    return V::object()
        .put("complete", V::boolean_value(chain.complete))
        .put("clusters", std::move(clusters))
        .put("cells", chain.cells);
}
class Observer {
    const ExfatCaptureRequest &request_;
    const RegionReader &reader_;
    de_block_space source_{};
    de_exfat_boot boot_{};
    Bytes boot_bytes_;
    std::vector<Region> regions_;
    std::vector<Record> records_;
    std::set<std::uint32_t> occupied_;
    Chain root_chain_, bitmap_chain_, upcase_chain_;
    std::size_t reads_ = 0, read_bytes_ = 0, retained_ = 0, output_used_ = 8192;
    std::size_t rereads_ = 0, labels_ = 0;
    bool root_complete_ = false, root_end_ = false, cardinality_ = false;
    bool bitmap_valid_ = false, upcase_valid_ = false, membership_ = false, reread_equal_ = false;
    bool boot_observed_ = false;
    V bitmap_descriptors_ = V::array(), upcase_descriptors_ = V::array();
    V bitmap_facts_ = V::object(), upcase_facts_ = V::object();

    void retain(std::size_t bytes) {
        if (bytes > request_.limits.retained_bytes - retained_)
            stop("exfat_retained_budget");
        retained_ += bytes;
    }
    void output(std::size_t bytes) {
        if (bytes > request_.limits.output_bytes - output_used_)
            stop("exfat_output_budget");
        output_used_ += bytes;
    }
    de_view fetch(std::uint64_t absolute, std::size_t length) {
        if (!length || absolute < request_.volume_offset ||
            absolute - request_.volume_offset > request_.volume_bytes ||
            length > request_.volume_bytes - (absolute - request_.volume_offset))
            stop("exfat_read_bounds");
        if (reads_ == request_.limits.read_requests ||
            length > request_.limits.read_bytes - read_bytes_)
            stop("exfat_read_budget");
        de_block_extent blocks{};
        de_byte_extent extent{};
        const auto start = portable(absolute), size = portable(length);
        checked(de_extent_make(&source_, &start, &size, &blocks));
        checked(de_extent_to_bytes(&blocks, &extent));
        ++reads_;
        read_bytes_ += length;
        de_view borrowed{};
        try {
            borrowed = reader_(extent);
        } catch (...) {
            stop("exfat_reader_failure");
        }
        if (borrowed.size != length || !borrowed.data)
            stop("exfat_read_length");
        return borrowed;
    }
    Bytes read(std::uint64_t relative, std::size_t length) {
        retain(length);
        output(192);
        const auto absolute = add(request_.volume_offset, relative);
        const auto borrowed = fetch(absolute, length);
        Bytes copy(borrowed.data, borrowed.data + length);
        for (const auto &prior : regions_) {
            const auto begin = std::max(absolute, prior.start);
            const auto end = std::min(add(absolute, length), add(prior.start, prior.bytes.size()));
            if (begin < end &&
                !std::equal(copy.begin() + static_cast<std::size_t>(begin - absolute),
                            copy.begin() + static_cast<std::size_t>(end - absolute),
                            prior.bytes.begin() + static_cast<std::size_t>(begin - prior.start)))
                stop("exfat_source_changed");
        }
        regions_.push_back(Region{absolute, copy});
        return copy;
    }
    std::uint64_t cluster_offset(std::uint32_t cluster) const {
        return add(native(boot_.heap_offset_bytes), mul(cluster - 2, boot_.cluster_bytes));
    }
    void chain(Chain &result, std::uint32_t first, std::uint64_t length, bool root) {
        std::set<std::uint32_t> visited;
        auto cluster = first;
        for (;;) {
            if (cluster < 2 || cluster > boot_.cluster_count + 1)
                stop("exfat_chain_cluster");
            if (!visited.insert(cluster).second)
                stop("exfat_chain_cycle");
            if (occupied_.size() == request_.limits.clusters)
                stop("exfat_chain_budget");
            if (!occupied_.insert(cluster).second)
                stop("exfat_chain_crosslink");
            output(192);
            result.clusters.push_back(cluster);
            if (root && mul(result.clusters.size(), boot_.cluster_bytes) > 268435456)
                stop("exfat_root_length");
            const auto table = add(mul(boot_.fat_offset, boot_.sector_bytes),
                                   mul(boot_.active_fat, native(boot_.fat_bytes)));
            const auto offset = add(table, mul(cluster, 4));
            const auto bytes = read(offset, 4);
            const de_view view{bytes.data(), bytes.size()};
            de_exfat_cell cell{};
            checked(de_exfat_cell_read(&view, boot_.cluster_count, cluster, &cell));
            result.cells.items.push_back(
                V::object()
                    .put("source_offset", exact(add(request_.volume_offset, offset)))
                    .put("index", exact(cell.index))
                    .put("value", exact(cell.value))
                    .put("kind", exact(static_cast<unsigned>(cell.kind))));
            if (cell.kind == DE_EXFAT_CELL_END)
                break;
            if (cell.kind != DE_EXFAT_CELL_NEXT)
                stop("exfat_chain_marker");
            cluster = cell.value;
        }
        if (!root) {
            const auto expected =
                length / boot_.cluster_bytes + (length % boot_.cluster_bytes != 0);
            if (expected != result.clusters.size())
                stop("exfat_chain_length");
        }
        result.complete = true;
    }
    void collect_root() {
        for (auto cluster : root_chain_.clusters) {
            const auto start = cluster_offset(cluster);
            for (std::uint32_t at = 0; at < boot_.cluster_bytes;) {
                const auto amount = std::min<std::uint32_t>(8192, boot_.cluster_bytes - at);
                const auto bytes = read(add(start, at), amount);
                for (std::size_t n = 0; n < bytes.size(); n += 32) {
                    if (records_.size() == request_.limits.records)
                        stop("exfat_record_budget");
                    retain(32);
                    output(256);
                    Record record{};
                    record.start = add(request_.volume_offset, add(start, at + n));
                    std::copy_n(bytes.begin() + n, 32, record.bytes.begin());
                    records_.push_back(record);
                    if (!record.bytes[0]) {
                        root_end_ = true;
                        root_complete_ = true;
                        return;
                    }
                }
                at += amount;
            }
        }
        root_complete_ = true;
    }
    void interpret_root(de_exfat_bitmap &selected, de_exfat_upcase_descriptor &upcase) {
        std::set<unsigned> identifiers;
        for (std::size_t at = 0; at < records_.size(); ++at) {
            const auto &record = records_[at];
            const de_view view{record.bytes.data(), record.bytes.size()};
            de_exfat_slot slot{};
            checked(de_exfat_slot_read(&view, &slot));
            if (slot.kind == DE_EXFAT_DIR_END || slot.kind == DE_EXFAT_DIR_UNUSED)
                continue;
            if (slot.kind == DE_EXFAT_DIR_BITMAP) {
                de_exfat_bitmap value{};
                checked(de_exfat_bitmap_read(&view, boot_.cluster_count,
                                             boot_.sector_shift + boot_.cluster_shift,
                                             boot_.fat_count, &value));
                output(512);
                bitmap_descriptors_.items.push_back(
                    V::object()
                        .put("source_offset", exact(record.start))
                        .put("identifier", exact(value.identifier))
                        .put("first_cluster", exact(value.first_cluster))
                        .put("data_length", exact(native(value.data_length)))
                        .put("issues", exact(value.issues))
                        .put("valid", V::boolean_value(value.valid != 0)));
                if (!value.valid || !identifiers.insert(value.identifier).second)
                    stop("exfat_bitmap_descriptor");
                if (value.identifier == boot_.active_fat)
                    selected = value;
            } else if (slot.kind == DE_EXFAT_DIR_UPCASE) {
                de_exfat_upcase_descriptor value{};
                checked(de_exfat_upcase_descriptor_read(
                    &view, boot_.cluster_count, boot_.sector_shift + boot_.cluster_shift, &value));
                output(512);
                upcase_descriptors_.items.push_back(
                    V::object()
                        .put("source_offset", exact(record.start))
                        .put("first_cluster", exact(value.first_cluster))
                        .put("data_length", exact(native(value.data_length)))
                        .put("checksum", exact(value.table_checksum))
                        .put("issues", exact(value.issues))
                        .put("valid", V::boolean_value(value.valid != 0)));
                if (!value.valid || upcase_descriptors_.items.size() != 1)
                    stop("exfat_upcase_descriptor");
                upcase = value;
            } else if (slot.kind == DE_EXFAT_DIR_LABEL) {
                if (slot.issues || ++labels_ > 1)
                    stop("exfat_label_descriptor");
            } else if (slot.kind == DE_EXFAT_DIR_FILE) {
                const auto count = static_cast<std::size_t>(slot.secondary_count) + 1;
                if (count > records_.size() - at)
                    stop("exfat_root_file_set");
                Bytes bytes;
                bytes.reserve(count * 32);
                for (std::size_t n = 0; n < count; ++n)
                    bytes.insert(bytes.end(), records_[at + n].bytes.begin(),
                                 records_[at + n].bytes.end());
                const de_view set_view{bytes.data(), bytes.size()};
                de_exfat_file_set value{};
                checked(de_exfat_file_set_read(&set_view, boot_.cluster_count,
                                               boot_.sector_shift + boot_.cluster_shift,
                                               bytes.size(), &value));
                if (!value.associated)
                    stop("exfat_root_file_set");
                at += count - 1;
            } else if (slot.secondary)
                stop("exfat_orphan_secondary");
            else if (!slot.benign || slot.kind == DE_EXFAT_DIR_INVALID)
                stop("exfat_critical_root_entry");
        }
        if (identifiers.size() != boot_.fat_count || upcase_descriptors_.items.size() != 1)
            stop("exfat_root_cardinality");
        cardinality_ = true;
    }
    Bytes system_bytes(const Chain &chain, std::uint64_t length) {
        if (length > request_.limits.retained_bytes - retained_)
            stop("exfat_retained_budget");
        const auto size = static_cast<std::size_t>(length);
        retain(size);
        Bytes result;
        result.reserve(size);
        for (auto cluster : chain.clusters) {
            const auto start = cluster_offset(cluster);
            const auto remaining = size - result.size();
            const auto amount = std::min<std::size_t>(remaining, boot_.cluster_bytes);
            for (std::size_t at = 0; at < amount;) {
                const auto n = std::min<std::size_t>(8192, amount - at);
                const auto bytes = read(add(start, at), n);
                result.insert(result.end(), bytes.begin(), bytes.end());
                at += n;
            }
        }
        return result;
    }
    void bitmap(const de_exfat_bitmap &descriptor) {
        const auto length = native(descriptor.data_length);
        const auto bytes = system_bytes(bitmap_chain_, length);
        de_u32 available = 0, unavailable = 0;
        std::uint64_t bit = 0;
        for (std::size_t at = 0; bit < boot_.cluster_count; at += 8192) {
            const auto n = std::min<std::size_t>(8192, bytes.size() - at);
            const auto count =
                static_cast<de_u32>(std::min<std::uint64_t>(n * 8, boot_.cluster_count - bit));
            const de_view view{bytes.data() + at, n};
            const auto offset = portable(at);
            de_exfat_bitmap_interval interval{};
            checked(de_exfat_bitmap_count(&view, &offset, &descriptor.data_length,
                                          boot_.cluster_count, static_cast<de_u32>(bit + 2), count,
                                          count, &interval));
            available += interval.available;
            unavailable += interval.unavailable;
            bit += count;
        }
        bitmap_valid_ = true;
        bitmap_facts_.put("bytes", exact(length))
            .put("sha256", V::string(digest(bytes)))
            .put("available", exact(available))
            .put("unavailable", exact(unavailable));
        for (auto cluster : occupied_) {
            const auto index = static_cast<std::uint64_t>(cluster) - 2;
            if (!(bytes[static_cast<std::size_t>(index / 8)] & (1U << (index % 8))))
                stop("exfat_system_cluster_available");
        }
        membership_ = true;
    }
    void upcase(const de_exfat_upcase_descriptor &descriptor) {
        const auto bytes = system_bytes(upcase_chain_, native(descriptor.data_length));
        if (request_.upcase_format == ExfatUpcaseFormat::Automatic)
            output(2048);
        try {
            evaluate_exfat_upcase(bytes, descriptor.table_checksum, request_.upcase_format,
                                 upcase_facts_, [this](std::size_t n) { retain(n); });
        } catch (const ExfatUpcaseError &error) { stop(error.what()); }
        upcase_valid_ = true;
    }
    void reread() {
        for (const auto &region : regions_) {
            const auto borrowed = fetch(region.start, region.bytes.size());
            if (!std::equal(region.bytes.begin(), region.bytes.end(), borrowed.data))
                stop("exfat_source_changed");
            ++rereads_;
        }
        reread_equal_ = true;
    }
    V result(const std::string &failure) const {
        auto regions = V::array(), records = V::array();
        for (const auto &region : regions_)
            regions.items.push_back(V::object()
                                        .put("source_offset", exact(region.start))
                                        .put("bytes", exact(region.bytes.size()))
                                        .put("sha256", V::string(digest(region.bytes))));
        for (const auto &record : records_)
            records.items.push_back(
                V::object()
                    .put("source_offset", exact(record.start))
                    .put("raw", V::string(hex(record.bytes.data(), record.bytes.size()))));
        auto boot = V::object().put("observed", V::boolean_value(boot_observed_));
        if (boot_observed_)
            boot.put("issues", exact(boot_.issues))
                .put("usable_geometry", V::boolean_value(boot_.usable_geometry != 0))
                .put("checksum_valid", V::boolean_value(boot_.checksum_valid != 0))
                .put("active_fat", exact(boot_.active_fat))
                .put("fat_count", exact(boot_.fat_count))
                .put("cluster_count", exact(boot_.cluster_count))
                .put("cluster_bytes", exact(boot_.cluster_bytes))
                .put("flags", exact(boot_.flags))
                .put("percent_in_use", exact(boot_.percent_in_use))
                .put("revision", exact(boot_.revision))
                .put("serial", exact(boot_.serial))
                .put("volume_bytes", exact(native(boot_.volume_bytes)))
                .put("heap_offset_bytes", exact(native(boot_.heap_offset_bytes)))
                .put("fat_offset_bytes", exact(mul(boot_.fat_offset, boot_.sector_bytes)))
                .put("fat_bytes", exact(native(boot_.fat_bytes)))
                .put("texfat_structure", V::boolean_value(boot_.texfat_structure != 0));
        auto diagnostics = V::array();
        if (!failure.empty())
            diagnostics.items.push_back(V::string(failure));
        const auto schema = request_.upcase_format == ExfatUpcaseFormat::Automatic
                                ? "org.disked.exfat-root-observation/2"
                                : "org.disked.exfat-root-observation/1";
        auto out = V::object()
                       .put("schema", V::string(schema))
                       .put("applicability_scope", V::string("root-and-active-system-metadata"))
                       .put("atomic_snapshot", V::boolean_value(false))
                       .put("current_source_authority", V::boolean_value(false))
                       .put("source_id", V::string(request_.source_id))
                       .put("epoch", exact(request_.epoch))
                       .put("source_bytes", exact(request_.source_bytes))
                       .put("volume_offset", exact(request_.volume_offset))
                       .put("volume_bytes", exact(request_.volume_bytes))
                       .put("complete", V::boolean_value(failure.empty()))
                       .put("applicable",
                            V::boolean_value(failure.empty() && cardinality_ && bitmap_valid_ &&
                                             upcase_valid_ && membership_ && reread_equal_))
                       .put("diagnostics", std::move(diagnostics))
                       .put("boot", std::move(boot))
                       .put("root_complete", V::boolean_value(root_complete_))
                       .put("root_end_marker", V::boolean_value(root_end_))
                       .put("cardinality_valid", V::boolean_value(cardinality_))
                       .put("root_chain", chain_value(root_chain_))
                       .put("bitmap_chain", chain_value(bitmap_chain_))
                       .put("upcase_chain", chain_value(upcase_chain_))
                       .put("bitmap_descriptors", bitmap_descriptors_)
                       .put("upcase_descriptors", upcase_descriptors_)
                       .put("bitmap", bitmap_facts_)
                       .put("upcase", upcase_facts_)
                       .put("system_membership", V::boolean_value(membership_))
                       .put("reread_equal", V::boolean_value(reread_equal_))
                       .put("regions", std::move(regions))
                       .put("root_records", std::move(records))
                       .put("read_requests", exact(reads_))
                       .put("read_bytes", exact(read_bytes_))
                       .put("retained_bytes", exact(retained_))
                       .put("rereads", exact(rereads_));
        if (request_.upcase_format == ExfatUpcaseFormat::Automatic)
            out.put("upcase_format", V::string("auto"));
        else
            out.put("compressed_upcase",
                    V::boolean_value(request_.upcase_format == ExfatUpcaseFormat::Compressed));
        if (json::dump(out, output_limits()).size() > request_.limits.output_bytes)
            throw std::runtime_error("exfat_output_accounting");
        return out;
    }

  public:
    Observer(const ExfatCaptureRequest &request, const RegionReader &reader)
        : request_(request), reader_(reader) {
        validate_exfat_capture_request(request);
        if (!reader)
            throw std::invalid_argument("exfat_reader_required");
        const auto length = portable(request.source_bytes);
        checked(de_space_from_bytes(request.source_id.data(), request.source_id.size(), &length, 1,
                                    &source_));
    }
    V run() {
        std::string failure;
        try {
            const auto prefix = read(0, 512);
            const auto shift = prefix[108];
            if (shift < 9 || shift > 12)
                stop("exfat_sector_shift");
            retain(static_cast<std::size_t>(12) << shift);
            boot_bytes_ = read(0, static_cast<std::size_t>(12) << shift);
            const de_view view{boot_bytes_.data(), boot_bytes_.size()};
            const auto available = portable(request_.volume_bytes);
            checked(de_exfat_boot_read(&view, &available, 0, &boot_));
            boot_observed_ = true;
            if (!boot_.usable_geometry || !boot_.checksum_valid || !boot_.active_fat_known)
                stop("exfat_boot_invalid");
            chain(root_chain_, boot_.root_cluster, 0, true);
            collect_root();
            de_exfat_bitmap selected{};
            de_exfat_upcase_descriptor table{};
            interpret_root(selected, table);
            chain(bitmap_chain_, selected.first_cluster, native(selected.data_length), false);
            chain(upcase_chain_, table.first_cluster, native(table.data_length), false);
            bitmap(selected);
            upcase(table);
            reread();
        } catch (const Stop &s) {
            failure = s.code;
        }
        return result(failure);
    }
};
} // namespace
void validate_exfat_capture_request(const ExfatCaptureRequest &r) {
    exfat_upcase_format_name(r.upcase_format);
    if (!r.epoch || !r.source_bytes || r.volume_bytes < 512 || r.source_id.empty() ||
        r.source_id.size() > 128 || r.source_id.find('\0') != std::string::npos ||
        !json::valid_utf8(r.source_id))
        throw std::invalid_argument("exfat_capture_inputs");
    if (r.volume_offset > r.source_bytes || r.volume_bytes > r.source_bytes - r.volume_offset)
        throw std::invalid_argument("exfat_capture_window");
    const auto &l = r.limits;
    if (!l.read_requests || l.read_requests > 8192 || !l.read_bytes || l.read_bytes > 2097152 ||
        !l.clusters || l.clusters > 4096 || !l.records || l.records > 4096 || !l.retained_bytes ||
        l.retained_bytes > 1048576 || l.output_bytes < 16384 || l.output_bytes > 1048576)
        throw std::invalid_argument("exfat_capture_limits");
}
V observe_exfat_volume(const ExfatCaptureRequest &request, const RegionReader &reader) {
    return Observer(request, reader).run();
}
} // namespace disked
