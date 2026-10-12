#include "fat_capture.h"
#include "portable/fat/fat.h"
#include <algorithm>
#include <deque>
#include <map>
#include <set>
#include <utility>
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
void checked(int status) {
    if (status)
        stop("fat_capture_internal");
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
de_u64 portable(std::uint64_t n) {
    de_u64 out{};
    const auto s = std::to_string(n);
    checked(de_u64_parse(s.data(), s.size(), &out));
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    checked(de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    auto left = portable(a), right = portable(b);
    de_u64 out{};
    if (de_u64_add(&left, &right, &out))
        stop("fat_extent_overflow");
    return native(out);
}
std::string hex(const unsigned char *p, std::size_t n) {
    const char alphabet[] = "0123456789abcdef";
    std::string out;
    out.reserve(n * 2);
    for (std::size_t i = 0; i < n; ++i) {
        out += alphabet[p[i] >> 4];
        out += alphabet[p[i] & 15];
    }
    return out;
}
json::Limits json_limits() {
    json::Limits l;
    l.bytes = 4194304;
    l.string_bytes = 2097152;
    l.values = 262144;
    l.depth = 64;
    return l;
}
std::size_t encoded(const V &v) {
    return json::dump(v, json_limits()).size();
}
V array_exact(const std::vector<std::uint64_t> &values) {
    auto out = V::array();
    for (auto n : values)
        out.items.push_back(exact(n));
    return out;
}

struct Node {
    V value = V::object(), cells = V::array(), extents = V::array(), orphans = V::array();
    std::vector<std::uint32_t> clusters;
    std::set<std::string> codes;
    std::uint32_t first = 0;
    std::uint64_t file_bytes = 0, allocated = 0;
    std::size_t depth = 0, parent = 0;
    bool directory = false, entries_complete = false, chain_complete = false;
    std::string chain = "not_observed";
};
struct CapturedRange {
    std::uint64_t start;
    Bytes bytes;
};

class Observer {
    const FatCaptureRequest &request_;
    const RegionReader &reader_;
    de_block_space source_{};
    de_fat_volume volume_{};
    Bytes boot_;
    std::map<std::pair<std::uint64_t, std::size_t>, CapturedRange> ranges_;
    std::deque<Node> nodes_;
    std::map<std::uint32_t, std::vector<std::size_t>> owners_;
    std::set<std::uint32_t> directories_;
    std::size_t reads_ = 0, read_bytes_ = 0, records_ = 0, total_clusters_ = 0, orphan_groups_ = 0,
                output_used_ = 12288;
    std::size_t active_ = 0;
    std::size_t omitted_nodes_ = 0;
    bool complete_ = true, consistent_ = true, overlap_equal_ = true;
    V diagnostics_ = V::array();

    de_fat_entry paged_cell(std::uint32_t index, std::uint32_t copy) {
        de_fat_cell_request wanted{};
        checked(de_fat_entry_request(volume_.bits, volume_.cluster_count, index, &wanted));
        const auto table_bytes = native(volume_.fat_bytes), within = native(wanted.offset);
        if (within > table_bytes || wanted.bytes > table_bytes - within)
            stop("fat_cell_extent");
        const auto table =
            static_cast<std::uint64_t>(volume_.reserved_sectors) * volume_.bytes_per_sector +
            static_cast<std::uint64_t>(copy) * table_bytes;
        unsigned char raw[4]{};
        for (std::size_t copied = 0; copied < wanted.bytes;) {
            const auto position = within + copied, page = position / 4096 * 4096;
            const auto length =
                static_cast<std::size_t>(std::min<std::uint64_t>(4096, table_bytes - page));
            const auto &bytes = read(add(table, page), length);
            const auto offset = static_cast<std::size_t>(position - page);
            const auto amount = std::min<std::size_t>(wanted.bytes - copied, length - offset);
            std::copy_n(bytes.begin() + offset, amount, raw + copied);
            copied += amount;
        }
        const de_view view{raw, wanted.bytes};
        de_fat_entry out{};
        checked(de_fat_cell_read(&view, volume_.bits, volume_.cluster_count, index, &out));
        return out;
    }

    V allocation() {
        // This phase cannot rewrite a completed tree's state. Coverage, copy
        // agreement and finding truncation remain independent observations.
        auto findings = V::array(), failures = V::array();
        std::size_t total_findings = 0, omitted = 0, differences = 0, raw_variants = 0;
        auto finding = [&](V value) {
            ++total_findings;
            const auto bytes = encoded(value) + 16;
            if (findings.items.size() == request_.limits.allocation_findings ||
                bytes > request_.limits.output_bytes - output_used_) {
                ++omitted;
                return;
            }
            charge(bytes);
            findings.items.push_back(std::move(value));
        };
        const auto copies =
            std::min<std::size_t>(volume_.fat_count, request_.limits.compare_copies);
        const auto capacity =
            std::min<std::size_t>(volume_.cluster_count, request_.limits.allocation_clusters);
        std::vector<de_fat_entry> cells;
        cells.reserve(capacity);
        std::size_t categories[8]{};
        const bool ownership = complete_ && consistent_;
        try {
            for (std::uint32_t index = 2; cells.size() < capacity; ++index) {
                const auto chosen = paged_cell(index, request_.fat_copy);
                auto variants = V::array();
                auto variant = [&](std::uint32_t copy, const de_fat_entry &entry) {
                    variants.items.push_back(V::object()
                                                 .put("copy", exact(copy))
                                                 .put("raw", exact(entry.raw_value))
                                                 .put("value", exact(entry.value)));
                };
                variant(request_.fat_copy, chosen);
                bool different = false, raw_different = false;
                std::size_t compared = 1;
                for (std::uint32_t copy = 0; copy < volume_.fat_count && compared < copies;
                     ++copy) {
                    if (copy == request_.fat_copy)
                        continue;
                    const auto other = paged_cell(index, copy);
                    variant(copy, other);
                    different = different || other.value != chosen.value;
                    raw_different = raw_different || other.raw_value != chosen.raw_value;
                    ++compared;
                }
                // Publication commits the entire requested comparison set.
                cells.push_back(chosen);
                ++categories[chosen.kind];
                if (different)
                    ++differences;
                if (raw_different)
                    ++raw_variants;
                if (different || raw_different)
                    finding(
                        V::object()
                            .put("code", V::string(different ? "fat_allocation_copy_disagreement"
                                                             : "fat_allocation_raw_variant"))
                            .put("cluster", exact(index))
                            .put("copies", std::move(variants)));
            }
            if (cells.size() < volume_.cluster_count)
                failures.items.push_back(V::string("fat_allocation_cluster_budget"));
        } catch (const Stop &error) {
            failures.items.push_back(V::string(error.code));
        }

        std::vector<std::uint32_t> incoming(cells.size(), 0);
        std::vector<unsigned char> colors(cells.size(), 0);
        std::size_t outside = 0, into_free = 0, into_bad = 0, into_reserved = 0;
        std::size_t unowned = 0, merges = 0, cycles = 0, cyclic_clusters = 0;
        for (std::size_t i = 0; i < cells.size(); ++i) {
            const auto &entry = cells[i];
            if ((entry.kind == DE_FAT_ENTRY_NEXT || entry.kind == DE_FAT_ENTRY_END) &&
                !owners_.count(static_cast<std::uint32_t>(i + 2))) {
                ++unowned;
                finding(V::object()
                            .put("code", V::string("fat_allocation_without_observed_owner"))
                            .put("cluster", exact(i + 2))
                            .put("value", exact(entry.value)));
            }
            if (entry.kind != DE_FAT_ENTRY_NEXT)
                continue;
            const auto target = static_cast<std::size_t>(entry.value - 2);
            if (target >= cells.size()) {
                ++outside;
                finding(V::object()
                            .put("code", V::string("fat_allocation_link_outside_coverage"))
                            .put("cluster", exact(i + 2))
                            .put("target", exact(entry.value)));
                continue;
            }
            ++incoming[target];
            const char *code = nullptr;
            if (cells[target].kind == DE_FAT_ENTRY_FREE) {
                ++into_free;
                code = "fat_allocation_link_into_free";
            } else if (cells[target].kind == DE_FAT_ENTRY_BAD) {
                ++into_bad;
                code = "fat_allocation_link_into_bad";
            } else if (cells[target].kind == DE_FAT_ENTRY_RESERVED) {
                ++into_reserved;
                code = "fat_allocation_link_into_reserved";
            }
            if (code)
                finding(V::object()
                            .put("code", V::string(code))
                            .put("cluster", exact(i + 2))
                            .put("target", exact(entry.value)));
        }
        for (std::size_t i = 0; i < cells.size(); ++i) {
            if (incoming[i] > 1) {
                ++merges;
                finding(V::object()
                            .put("code", V::string("fat_allocation_merge"))
                            .put("cluster", exact(i + 2))
                            .put("incoming", exact(incoming[i])));
            }
            if (colors[i])
                continue;
            std::vector<std::size_t> path;
            std::size_t cursor = i;
            while (cursor < cells.size() && colors[cursor] == 0) {
                colors[cursor] = 1;
                path.push_back(cursor);
                if (cells[cursor].kind != DE_FAT_ENTRY_NEXT) {
                    cursor = cells.size();
                    break;
                }
                cursor = static_cast<std::size_t>(cells[cursor].value - 2);
            }
            if (cursor < cells.size() && colors[cursor] == 1) {
                std::size_t length = 1;
                for (auto at = static_cast<std::size_t>(cells[cursor].value - 2); at != cursor;
                     at = static_cast<std::size_t>(cells[at].value - 2))
                    ++length;
                ++cycles;
                cyclic_clusters += length;
                finding(V::object()
                            .put("code", V::string("fat_allocation_cycle"))
                            .put("cluster", exact(cursor + 2))
                            .put("clusters", exact(length)));
            }
            for (auto visited : path)
                colors[visited] = 2;
        }
        const bool coverage = cells.size() == volume_.cluster_count;
        const bool comparison = coverage && copies == volume_.fat_count;
        return V::object()
            .put("expected_clusters", exact(volume_.cluster_count))
            .put("scanned_clusters", exact(cells.size()))
            .put("first_cluster", exact(2))
            .put("covered_end", exact(cells.size() + 2))
            .put("next_cluster", coverage ? V{} : exact(cells.size() + 2))
            .put("coverage_complete", V::boolean_value(coverage))
            .put("prefix_analysis_complete", V::boolean_value(true))
            .put("compared_copies", exact(cells.empty() ? 0 : copies))
            .put("comparison_complete", V::boolean_value(comparison))
            .put("different_cells", exact(differences))
            .put("raw_variant_cells", exact(raw_variants))
            .put("categories", V::object()
                                   .put("free", exact(categories[DE_FAT_ENTRY_FREE]))
                                   .put("next", exact(categories[DE_FAT_ENTRY_NEXT]))
                                   .put("end", exact(categories[DE_FAT_ENTRY_END]))
                                   .put("bad", exact(categories[DE_FAT_ENTRY_BAD]))
                                   .put("reserved", exact(categories[DE_FAT_ENTRY_RESERVED])))
            .put("links_outside_coverage", exact(outside))
            .put("links_into_free", exact(into_free))
            .put("links_into_bad", exact(into_bad))
            .put("links_into_reserved", exact(into_reserved))
            .put("merge_points", exact(merges))
            .put("cycle_components", exact(cycles))
            .put("cyclic_clusters", exact(cyclic_clusters))
            .put("prefix_graph_consistent",
                 V::boolean_value(!differences && !into_free && !into_bad && !into_reserved &&
                                  !merges && !cycles))
            .put("allocated_without_observed_owner", exact(unowned))
            .put("tree_ownership_complete", V::boolean_value(ownership))
            .put("unreferenced_allocation_qualified",
                 V::boolean_value(ownership && coverage && comparison && !differences &&
                                  overlap_equal_))
            .put("findings", std::move(findings))
            .put("total_findings", exact(total_findings))
            .put("omitted_findings", exact(omitted))
            .put("details_complete", V::boolean_value(!omitted))
            .put("diagnostics", std::move(failures));
    }

    void charge(std::size_t n) {
        if (n > request_.limits.output_bytes - output_used_)
            stop("fat_output_budget");
        output_used_ += n;
    }
    void detail_charge(const V &v) {
        charge(encoded(v) + 16);
    }
    void issue(Node &node, const char *code, bool incomplete = false) {
        node.codes.insert(code);
        consistent_ = false;
        if (incomplete)
            complete_ = false;
    }
    const Bytes &read(std::uint64_t relative, std::size_t length) {
        if (length > 4096 || relative > request_.volume_bytes ||
            length > request_.volume_bytes - relative)
            stop("fat_read_extent");
        const auto absolute = add(request_.volume_offset, relative);
        const auto key = std::make_pair(absolute, length);
        const auto existing = ranges_.find(key);
        if (existing != ranges_.end())
            return existing->second.bytes;
        if (reads_ == request_.limits.read_requests ||
            length > request_.limits.read_bytes - read_bytes_)
            stop("fat_read_budget");
        ++reads_;
        read_bytes_ += length;
        auto start = portable(absolute), count = portable(length);
        de_block_extent blocks{};
        de_byte_extent bytes{};
        checked(de_extent_make(&source_, &start, &count, &blocks));
        checked(de_extent_to_bytes(&blocks, &bytes));
        de_view view{};
        try {
            view = reader_(bytes);
        } catch (...) {
            stop("fat_reader_exception");
        }
        if ((!view.data && view.size) || view.size > length)
            stop("fat_reader_shape");
        CapturedRange range{absolute,
                            view.size ? Bytes(view.data, view.data + view.size) : Bytes{}};
        for (const auto &pair : ranges_) {
            const auto &old = pair.second;
            const auto first = std::max(range.start, old.start),
                       last = std::min(add(range.start, range.bytes.size()),
                                       add(old.start, old.bytes.size()));
            if (first < last &&
                !std::equal(range.bytes.begin() + static_cast<std::size_t>(first - range.start),
                            range.bytes.begin() + static_cast<std::size_t>(last - range.start),
                            old.bytes.begin() + static_cast<std::size_t>(first - old.start))) {
                overlap_equal_ = false;
                stop("fat_reader_overlap_changed");
            }
        }
        const auto inserted = ranges_.emplace(key, std::move(range));
        if (inserted.first->second.bytes.size() != length)
            stop("fat_reader_short");
        return inserted.first->second.bytes;
    }
    de_fat_entry cell(std::uint32_t index, Node &node) {
        de_fat_cell_request wanted{};
        checked(de_fat_entry_request(volume_.bits, volume_.cluster_count, index, &wanted));
        const auto table_bytes = native(volume_.fat_bytes), within = native(wanted.offset);
        if (within > table_bytes || wanted.bytes > table_bytes - within)
            stop("fat_cell_extent");
        auto fetch = [&](std::uint32_t copy) {
            const auto table =
                static_cast<std::uint64_t>(volume_.reserved_sectors) * volume_.bytes_per_sector +
                static_cast<std::uint64_t>(copy) * table_bytes;
            const auto &raw = read(add(table, within), wanted.bytes);
            de_view bytes{raw.data(), raw.size()};
            de_fat_entry out{};
            checked(de_fat_cell_read(&bytes, volume_.bits, volume_.cluster_count, index, &out));
            return out;
        };
        const auto chosen = fetch(request_.fat_copy);
        auto values = V::array();
        auto record = [&](std::uint32_t copy, const de_fat_entry &entry) {
            auto row = V::array();
            row.items.push_back(exact(copy));
            row.items.push_back(exact(entry.raw_value));
            values.items.push_back(std::move(row));
        };
        record(request_.fat_copy, chosen);
        std::size_t count = 1;
        for (std::uint32_t copy = 0;
             copy < volume_.fat_count && count < request_.limits.compare_copies; ++copy) {
            if (copy == request_.fat_copy)
                continue;
            const auto other = fetch(copy);
            record(copy, other);
            ++count;
            if (other.value != chosen.value)
                issue(node, "fat_copy_disagreement");
        }
        if (count < volume_.fat_count)
            issue(node, "fat_copy_comparison_budget", true);
        auto event = V::object()
                         .put("index", exact(index))
                         .put("value", exact(chosen.value))
                         .put("kind", exact(static_cast<std::uint64_t>(chosen.kind)))
                         .put("copies", std::move(values));
        detail_charge(event);
        node.cells.items.push_back(std::move(event));
        return chosen;
    }
    std::uint64_t cluster_offset(std::uint32_t cluster) const {
        if (cluster < 2 || cluster > volume_.cluster_count + 1)
            stop("fat_cluster_range");
        return add(native(volume_.data_offset_bytes),
                   static_cast<std::uint64_t>(cluster - 2) * volume_.cluster_bytes);
    }
    void chain(std::size_t id) {
        auto &node = nodes_[id];
        std::uint32_t current = node.first;
        std::set<std::uint32_t> seen;
        if (!current && !node.directory) {
            node.chain = "empty";
            node.chain_complete = node.file_bytes == 0;
            if (node.file_bytes)
                issue(node, "fat_file_chain_short");
            return;
        }
        if (current < 2 || current > volume_.cluster_count + 1) {
            node.chain = "invalid_start";
            issue(node, "fat_chain_start", true);
            return;
        }
        for (;;) {
            if (seen.count(current)) {
                node.chain = "cycle";
                issue(node, "fat_chain_cycle", true);
                break;
            }
            if (node.clusters.size() == request_.limits.chain_clusters ||
                total_clusters_ == request_.limits.total_clusters) {
                node.chain = "budget";
                issue(node, "fat_chain_budget", true);
                break;
            }
            charge(64); // Referenced-owner/cross-link representation reserve.
            seen.insert(current);
            node.clusters.push_back(current);
            ++total_clusters_;
            owners_[current].push_back(id);
            const auto start = cluster_offset(current);
            const auto &entry = cell(current, node);
            const auto logical = node.allocated;
            node.allocated += volume_.cluster_bytes;
            const auto content = node.directory
                                     ? 0
                                     : (logical < node.file_bytes
                                            ? std::min<std::uint64_t>(volume_.cluster_bytes,
                                                                      node.file_bytes - logical)
                                            : 0);
            auto extent = V::object()
                              .put("cluster", exact(current))
                              .put("volume_offset", exact(start))
                              .put("source_offset", exact(add(request_.volume_offset, start)))
                              .put("allocated_bytes", exact(volume_.cluster_bytes))
                              .put("file_offset", exact(logical))
                              .put("content_bytes", exact(content));
            detail_charge(extent);
            node.extents.items.push_back(std::move(extent));
            if (entry.kind == DE_FAT_ENTRY_NEXT) {
                current = entry.value;
                continue;
            }
            node.chain = entry.kind == DE_FAT_ENTRY_END    ? "end"
                         : entry.kind == DE_FAT_ENTRY_FREE ? "free"
                         : entry.kind == DE_FAT_ENTRY_BAD  ? "bad"
                                                           : "reserved";
            node.chain_complete = entry.kind == DE_FAT_ENTRY_END;
            if (!node.chain_complete)
                issue(node, "fat_chain_damaged", true);
            break;
        }
        if (!node.directory) {
            const auto expected = node.file_bytes / volume_.cluster_bytes +
                                  (node.file_bytes % volume_.cluster_bytes ? 1 : 0);
            if (node.allocated < node.file_bytes)
                issue(node, "fat_file_chain_short", true);
            if (node.clusters.size() > expected)
                issue(node, "fat_file_chain_excess");
        }
    }
    void orphan(Node &directory, Bytes &pending, std::vector<std::uint64_t> &positions,
                const char *reason) {
        if (pending.empty())
            return;
        if (orphan_groups_ == request_.limits.orphan_groups)
            stop("fat_orphan_budget");
        auto value = V::object()
                         .put("reason", V::string(reason))
                         .put("raw", V::string(hex(pending.data(), pending.size())))
                         .put("source_offsets", array_exact(positions));
        directory.orphans.items.push_back(std::move(value));
        ++orphan_groups_;
        issue(directory, "fat_orphan_names");
        pending.clear();
        positions.clear();
    }
    V metadata(const de_fat_dirent &entry, const Bytes &raw) const {
        return V::object()
            .put("raw", V::string(hex(raw.data(), raw.size())))
            .put("name_oem", V::string(hex(entry.name_field.data, entry.name_field.size)))
            .put("issues", exact(entry.issues))
            .put("attributes", exact(entry.attributes))
            .put("case_flags", exact(entry.case_flags))
            .put("lead_byte_escape", V::boolean_value(entry.lead_byte_escape != 0))
            .put("raw_cluster", exact(entry.raw_cluster))
            .put("cluster", exact(entry.cluster))
            .put("file_bytes", exact(entry.file_bytes))
            .put("dot", exact(static_cast<std::uint64_t>(entry.dot)))
            .put("creation_date", exact(entry.creation_date))
            .put("creation_time", exact(entry.creation_time))
            .put("creation_fraction", exact(entry.creation_fraction))
            .put("access_date", exact(entry.access_date))
            .put("write_date", exact(entry.write_date))
            .put("write_time", exact(entry.write_time));
    }
    void record(std::size_t parent, const Bytes &raw, std::uint64_t physical, std::size_t ordinal,
                Bytes &pending, std::vector<std::uint64_t> &positions, bool &ended) {
        auto &directory = nodes_[parent];
        if (records_ == request_.limits.records)
            stop("fat_record_budget");
        ++records_;
        de_view bytes{raw.data(), raw.size()};
        de_fat_dirent entry{};
        checked(de_fat_dirent_read(&bytes, volume_.bits, &entry));
        if (entry.kind == DE_FAT_DIRENT_END) {
            orphan(directory, pending, positions, "end_marker");
            ended = true;
            directory.entries_complete = true;
            return;
        }
        if (entry.kind == DE_FAT_DIRENT_LONG) {
            if ((entry.ordinal & 64) && !pending.empty())
                orphan(directory, pending, positions, "replaced_start");
            if (pending.size() == 640)
                orphan(directory, pending, positions, "slot_budget");
            if (pending.empty()) {
                if (orphan_groups_ == request_.limits.orphan_groups)
                    stop("fat_orphan_budget");
                charge(2048); // Reserve raw pending-name provenance, even on failure.
            }
            pending.insert(pending.end(), raw.begin(), raw.end());
            positions.push_back(add(request_.volume_offset, physical));
            return;
        }
        if (entry.kind == DE_FAT_DIRENT_DELETED) {
            orphan(directory, pending, positions, "deleted_boundary");
            auto item = V::object()
                            .put("reason", V::string("deleted_record"))
                            .put("raw", V::string(hex(raw.data(), raw.size())))
                            .put("source_offset", exact(add(request_.volume_offset, physical)));
            if (orphan_groups_ == request_.limits.orphan_groups)
                stop("fat_orphan_budget");
            detail_charge(item);
            directory.orphans.items.push_back(std::move(item));
            ++orphan_groups_;
            return;
        }
        Node child;
        child.parent = parent;
        child.depth = directory.depth + 1;
        child.first = entry.cluster;
        child.file_bytes = entry.file_bytes;
        child.directory = entry.kind == DE_FAT_DIRENT_DIRECTORY && !entry.dot;
        child.value =
            metadata(entry, raw)
                .put("id", exact(nodes_.size()))
                .put("parent", exact(parent))
                .put("kind", V::string(entry.kind == DE_FAT_DIRENT_DIRECTORY ? "directory"
                                       : entry.kind == DE_FAT_DIRENT_FILE    ? "file"
                                       : entry.kind == DE_FAT_DIRENT_VOLUME  ? "volume_label"
                                                                             : "invalid"))
                .put("depth", exact(child.depth))
                .put("directory_ordinal", exact(ordinal))
                .put("volume_record_offset", exact(physical))
                .put("source_record_offset", exact(add(request_.volume_offset, physical)));
        if (entry.issues)
            issue(child, "fat_entry_metadata");
        if (entry.dot) {
            child.value.put("kind", V::string("dot"));
            child.chain = "not_followed";
        }
        if (entry.kind == DE_FAT_DIRENT_VOLUME && parent != 0)
            issue(child, "fat_subdirectory_label");
        if (!pending.empty()) {
            de_view slots{pending.data(), pending.size()};
            de_fat_lfn name{};
            checked(de_fat_lfn_read(&slots, &bytes, volume_.bits, &name));
            auto units = V::array();
            for (std::size_t i = 0; i < name.unit_count; ++i)
                units.items.push_back(exact(name.units[i]));
            char display[1561];
            checked(de_fat_name_display(name.units, name.name_length, display, sizeof(display)));
            child.value.put("long_name",
                            V::object()
                                .put("raw_slots", V::string(hex(pending.data(), pending.size())))
                                .put("source_offsets", array_exact(positions))
                                .put("units", std::move(units))
                                .put("name_length", exact(name.name_length))
                                .put("issues", exact(name.issues))
                                .put("associated", V::boolean_value(name.associated != 0))
                                .put("unicode_valid", V::boolean_value(name.unicode_valid != 0))
                                .put("canonical", V::boolean_value(name.canonical_name != 0))
                                .put("display", V::string(display)));
            if (name.issues)
                issue(child, "fat_name_metadata");
        }
        if (nodes_.size() == request_.limits.nodes) {
            ++omitted_nodes_;
            stop("fat_node_budget");
        }
        try {
            charge(encoded(child.value) + 1024);
        } catch (const Stop &) {
            ++omitted_nodes_;
            throw;
        }
        nodes_.push_back(std::move(child));
        pending.clear();
        positions.clear();
    }
    void directory(std::size_t id) {
        auto &node = nodes_[id];
        if (node.depth > request_.limits.depth) {
            issue(node, "fat_depth_budget", true);
            return;
        }
        if (id && !directories_.insert(node.first).second) {
            issue(node, "fat_directory_reused", true);
            return;
        }
        Bytes pending;
        std::vector<std::uint64_t> positions;
        bool ended = false;
        std::size_t ordinal = 0;
        auto region = [&](std::uint64_t offset, std::uint64_t length) {
            for (std::uint64_t at = 0; at < length && !ended;) {
                const auto amount = static_cast<std::size_t>(
                    std::min<std::uint64_t>(volume_.bytes_per_sector, length - at));
                const auto &bytes = read(add(offset, at), amount);
                for (std::size_t pos = 0; pos + 32 <= bytes.size() && !ended; pos += 32) {
                    Bytes item(bytes.begin() + pos, bytes.begin() + pos + 32);
                    record(id, item, add(offset, at + pos), ordinal++, pending, positions, ended);
                }
                at += amount;
            }
        };
        try {
            if (id == 0 && volume_.bits != 32) {
                const auto offset =
                    static_cast<std::uint64_t>(volume_.reserved_sectors) *
                        volume_.bytes_per_sector +
                    static_cast<std::uint64_t>(volume_.fat_count) * native(volume_.fat_bytes);
                region(offset, static_cast<std::uint64_t>(volume_.root_entries) * 32);
                if (!ended)
                    node.entries_complete = true;
            } else {
                for (auto cluster : node.clusters) {
                    if (ended)
                        break;
                    region(cluster_offset(cluster), volume_.cluster_bytes);
                }
                if (!ended && node.chain_complete)
                    node.entries_complete = true;
            }
            orphan(node, pending, positions, "directory_end");
        } catch (const Stop &) {
            orphan(node, pending, positions, "interrupted");
            throw;
        }
    }

  public:
    Observer(const FatCaptureRequest &request, const RegionReader &reader)
        : request_(request), reader_(reader) {
        const auto &l = request.limits;
        if (!reader || !request.epoch || !request.source_bytes || !request.volume_bytes ||
            request.source_id.empty() || request.source_id.size() > 128 ||
            request.source_id.find('\0') != std::string::npos ||
            !json::valid_utf8(request.source_id))
            throw std::invalid_argument("fat_capture_inputs");
        if (request.volume_offset > request.source_bytes ||
            request.volume_bytes > request.source_bytes - request.volume_offset)
            throw std::invalid_argument("fat_capture_window");
        if (!l.nodes || l.nodes > 128 || !l.depth || l.depth > 8 || !l.chain_clusters ||
            l.chain_clusters > 1024 || !l.total_clusters || l.total_clusters > 4096 || !l.records ||
            l.records > 4096 || !l.read_requests || l.read_requests > 8192 || !l.read_bytes ||
            l.read_bytes > 2097152 || !l.orphan_groups || l.orphan_groups > 128 ||
            l.output_bytes < 16384 || l.output_bytes > 1048576 || !l.compare_copies ||
            l.compare_copies > 16 || !l.allocation_clusters || l.allocation_clusters > 262144 ||
            !l.allocation_findings || l.allocation_findings > 128)
            throw std::invalid_argument("fat_capture_limits");
        if (request.allocation_scan)
            output_used_ += 2048; // Reserve the summary even if tree/detail budgets stop.
        const auto bytes = portable(request.source_bytes);
        checked(
            de_space_init(request.source_id.data(), request.source_id.size(), &bytes, 1, &source_));
    }
    V run() {
        try {
            boot_ = read(0, 512);
            const auto available = portable(request_.volume_bytes);
            de_view boot{boot_.data(), boot_.size()};
            checked(de_fat_volume_read(&boot, &available, &volume_));
            if (volume_.bytes_per_sector > 512 && volume_.bytes_per_sector <= 4096) {
                boot_ = read(0, volume_.bytes_per_sector);
                boot = {boot_.data(), boot_.size()};
                checked(de_fat_volume_read(&boot, &available, &volume_));
            }
            if (!volume_.usable_layout)
                stop("fat_layout_unusable");
            if (request_.fat_copy >= volume_.fat_count)
                stop("fat_copy_range");
            Node root;
            root.directory = true;
            root.first = volume_.root_cluster;
            root.value = V::object()
                             .put("id", exact(0))
                             .put("kind", V::string("root"))
                             .put("depth", exact(0));
            charge(encoded(root.value) + 1024);
            nodes_.push_back(std::move(root));
            cell(0, nodes_[0]);
            cell(1, nodes_[0]);
            if (!volume_.mirrored && volume_.bits == 32 &&
                request_.fat_copy != (volume_.flags & 15))
                issue(nodes_[0], "fat_inactive_copy_selected");
            if (volume_.bits == 32)
                directories_.insert(volume_.root_cluster);
            for (std::size_t id = 0; id < nodes_.size(); ++id) {
                active_ = id;
                auto &node = nodes_[id];
                const auto *kind = node.value.find("kind");
                if (node.directory && node.depth > request_.limits.depth) {
                    issue(node, "fat_depth_budget", true);
                    continue;
                }
                if (kind->text == "file" || node.directory) {
                    if (!(id == 0 && volume_.bits != 32))
                        chain(id);
                    else {
                        node.chain = "fixed_root";
                        node.chain_complete = true;
                    }
                }
                if (node.directory)
                    directory(id);
            }
        } catch (const Stop &error) {
            complete_ = false;
            consistent_ = false;
            diagnostics_.items.push_back(V::object().put("code", V::string(error.code)));
            if (active_ < nodes_.size()) {
                nodes_[active_].codes.insert(error.code);
                if (nodes_[active_].chain == "not_observed")
                    nodes_[active_].chain = "incomplete";
            }
        }
        auto cross = V::array();
        for (const auto &pair : owners_)
            if (pair.second.size() > 1) {
                auto ids = V::array();
                for (auto id : pair.second) {
                    ids.items.push_back(exact(id));
                    issue(nodes_[id], "fat_cross_link");
                }
                cross.items.push_back(
                    V::object().put("cluster", exact(pair.first)).put("owners", std::move(ids)));
            }
        V scanned;
        if (request_.allocation_scan && volume_.usable_layout &&
            request_.fat_copy < volume_.fat_count)
            scanned = allocation();
        auto nodes = V::array();
        for (auto &n : nodes_) {
            auto codes = V::array();
            for (const auto &code : n.codes)
                codes.items.push_back(V::string(code));
            n.value.put("chain", V::string(n.chain))
                .put("chain_complete", V::boolean_value(n.chain_complete))
                .put("allocated_bytes", exact(n.allocated))
                .put("cells", std::move(n.cells))
                .put("extents", std::move(n.extents))
                .put("entries_complete", V::boolean_value(n.entries_complete))
                .put("orphan_records", std::move(n.orphans))
                .put("diagnostics", std::move(codes));
            nodes.items.push_back(std::move(n.value));
        }
        auto geometry = V::object()
                            .put("raw_boot", V::string(hex(boot_.data(), boot_.size())))
                            .put("issues", exact(volume_.issues))
                            .put("usable_layout", V::boolean_value(volume_.usable_layout != 0))
                            .put("bits", exact(static_cast<std::uint64_t>(volume_.bits)))
                            .put("sector_bytes", exact(volume_.bytes_per_sector))
                            .put("cluster_bytes", exact(volume_.cluster_bytes))
                            .put("clusters", exact(volume_.cluster_count))
                            .put("fat_copies", exact(volume_.fat_count));
        auto out = V::object()
                       .put("schema", V::string("org.disked.fat-volume-observation/1"))
                       .put("source_id", V::string(request_.source_id))
                       .put("capture_epoch", exact(request_.epoch))
                       .put("volume_offset", exact(request_.volume_offset))
                       .put("volume_bytes", exact(request_.volume_bytes))
                       .put("fat_copy", exact(request_.fat_copy))
                       .put("geometry", std::move(geometry))
                       .put("nodes", std::move(nodes))
                       .put("cross_links", std::move(cross))
                       .put("selected_tree_complete", V::boolean_value(complete_))
                       .put("observed_metadata_consistent", V::boolean_value(consistent_))
                       .put("allocation_scope", V::string("observed-tree-only"))
                       .put("diagnostics", std::move(diagnostics_))
                       .put("reads", V::object()
                                         .put("requests", exact(reads_))
                                         .put("requested_bytes", exact(read_bytes_))
                                         .put("regions", exact(ranges_.size()))
                                         .put("overlap_equal", V::boolean_value(overlap_equal_)))
                       .put("directory_records", exact(records_))
                       .put("observed_clusters", exact(total_clusters_))
                       .put("omitted_nodes", exact(omitted_nodes_))
                       .put("filesystem_health_qualified", V::boolean_value(false))
                       .put("authorizes_effects", V::boolean_value(false))
                       .put("product_dispatch_admitted", V::boolean_value(false));
        if (request_.allocation_scan) {
            const bool all =
                scanned.find("coverage_complete") && scanned.find("coverage_complete")->boolean;
            const bool comparison =
                scanned.find("comparison_complete") && scanned.find("comparison_complete")->boolean;
            const bool graph = scanned.find("prefix_graph_consistent") &&
                               scanned.find("prefix_graph_consistent")->boolean;
            out.put("tree_metadata_consistent", V::boolean_value(consistent_))
                .put("observed_metadata_consistent",
                     V::boolean_value(consistent_ && all && comparison && graph && overlap_equal_))
                .put("allocation_scope", V::string(scanned.kind == V::Kind::null ? "not-observed"
                                                   : all ? "all-data-clusters"
                                                         : "data-cluster-prefix"))
                .put("allocation_scan", std::move(scanned));
        }
        if (encoded(out) > request_.limits.output_bytes)
            throw std::runtime_error("fat_output_accounting");
        return out;
    }
};
} // namespace
json::Value observe_fat_volume(const FatCaptureRequest &request, const RegionReader &reader) {
    return Observer(request, reader).run();
}
} // namespace disked
