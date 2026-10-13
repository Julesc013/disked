#include "fat_content.h"
#include "portable/fat/fat.h"
#include <algorithm>
#include <array>
#include <limits>
#include <set>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
[[noreturn]] void fail(const char *code) {
    throw FatContentError(code);
}
void require(bool condition, const char *code = "fat_content_metadata") {
    if (!condition)
        fail(code);
}
const V &field(const V &v, const char *key) {
    require(v.kind == V::Kind::object);
    const auto *p = v.find(key);
    require(p != nullptr);
    return *p;
}
std::uint64_t integer(const V &v) {
    require(v.kind == V::Kind::string && json::decimal_u64(v.text));
    return std::stoull(v.text);
}
std::uint64_t integer(const V &v, const char *key) {
    return integer(field(v, key));
}
bool boolean(const V &v, const char *key) {
    const auto &p = field(v, key);
    require(p.kind == V::Kind::boolean);
    return p.boolean;
}
void text(const V &v, const char *key, const std::string &expected) {
    const auto &p = field(v, key);
    require(p.kind == V::Kind::string && p.text == expected);
}
const std::vector<V> &array(const V &v, const char *key, std::size_t maximum) {
    const auto &p = field(v, key);
    require(p.kind == V::Kind::array && p.items.size() <= maximum);
    return p.items;
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    require(b <= std::numeric_limits<std::uint64_t>::max() - a, "fat_content_overflow");
    return a + b;
}
std::uint64_t multiply(std::uint64_t a, std::uint64_t b) {
    require(!b || a <= std::numeric_limits<std::uint64_t>::max() / b, "fat_content_overflow");
    return a * b;
}
de_u64 portable(std::uint64_t n) {
    de_u64 out{};
    const auto value = std::to_string(n);
    require(!de_u64_parse(value.data(), value.size(), &out));
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char value[21];
    require(!de_u64_format(&n, value, sizeof(value)));
    return std::stoull(value);
}
unsigned digit(char c) {
    if (c >= '0' && c <= '9')
        return static_cast<unsigned>(c - '0');
    if (c >= 'a' && c <= 'f')
        return static_cast<unsigned>(c - 'a' + 10);
    fail("fat_content_metadata");
}
Bytes unhex(const V &v, const char *key, std::size_t size) {
    const auto &p = field(v, key);
    require(p.kind == V::Kind::string && p.text.size() == size * 2);
    Bytes out(size);
    for (std::size_t i = 0; i < size; ++i)
        out[i] = static_cast<unsigned char>(digit(p.text[i * 2]) * 16 + digit(p.text[i * 2 + 1]));
    return out;
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const Bytes &bytes) {
    static const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (auto b : bytes) {
        out += digits[b >> 4];
        out += digits[b & 15];
    }
    return out;
}
de_fat_entry decode_cell(std::uint64_t raw, std::uint32_t index, const de_fat_volume &volume) {
    const auto maximum = volume.bits == 32 ? 0xffffffffull : 0xffffull;
    require(raw <= maximum);
    // FAT12 receipts retain the original two-byte packed window, including
    // neighbouring nibble bits. Apply odd/even selection only in the decoder.
    std::array<unsigned char, 4> bytes{};
    for (std::size_t i = 0; i < bytes.size(); ++i)
        bytes[i] = static_cast<unsigned char>(raw >> (i * 8));
    de_view view{bytes.data(), volume.bits == 32 ? 4u : 2u};
    de_fat_entry entry{};
    require(!de_fat_cell_read(&view, volume.bits, volume.cluster_count, index, &entry));
    return entry;
}
} // namespace

FatContentMap prepare_fat_content(const V &observation, std::uint64_t node_id,
                                  const FatContentBinding &expected) {
    require(!expected.source_id.empty() && expected.source_id.size() <= 128 &&
                expected.source_id.find('\0') == std::string::npos &&
                json::valid_utf8(expected.source_id) && expected.epoch && expected.source_bytes &&
                expected.volume_bytes >= 512,
            "fat_content_binding");
    require(add(expected.volume_offset, expected.volume_bytes) <= expected.source_bytes,
            "fat_content_binding");
    text(observation, "schema", "org.disked.fat-volume-observation/1");
    text(observation, "source_id", expected.source_id);
    require(integer(observation, "capture_epoch") == expected.epoch &&
                integer(observation, "volume_offset") == expected.volume_offset &&
                integer(observation, "volume_bytes") == expected.volume_bytes &&
                integer(observation, "fat_copy") == expected.fat_copy,
            "fat_content_binding");
    require(boolean(field(observation, "reads"), "overlap_equal"), "fat_content_metadata_changed");
    const auto &geometry = field(observation, "geometry");
    const auto sector = integer(geometry, "sector_bytes");
    require(sector >= 512 && sector <= 4096 && !(sector & (sector - 1)), "fat_content_geometry");
    auto boot = unhex(geometry, "raw_boot", static_cast<std::size_t>(sector));
    de_view boot_view{boot.data(), boot.size()};
    auto available = portable(expected.volume_bytes);
    de_fat_volume volume{};
    require(!de_fat_volume_read(&boot_view, &available, &volume) && volume.usable_layout &&
                boolean(geometry, "usable_layout") && expected.fat_copy < volume.fat_count &&
                volume.fat_count <= 16,
            "fat_content_geometry");
    require(integer(geometry, "bits") == static_cast<std::uint64_t>(volume.bits) &&
                integer(geometry, "sector_bytes") == volume.bytes_per_sector &&
                integer(geometry, "cluster_bytes") == volume.cluster_bytes &&
                integer(geometry, "clusters") == volume.cluster_count &&
                integer(geometry, "fat_copies") == volume.fat_count &&
                integer(geometry, "issues") == volume.issues,
            "fat_content_geometry");
    const auto &nodes = array(observation, "nodes", 128);
    require(node_id < nodes.size(), "fat_content_node");
    for (std::size_t i = 0; i < nodes.size(); ++i)
        require(integer(nodes[i], "id") == i, "fat_content_node");
    const auto &node = nodes[static_cast<std::size_t>(node_id)];
    text(node, "kind", "file");
    auto record = unhex(node, "raw", 32);
    de_view record_view{record.data(), record.size()};
    de_fat_dirent file{};
    require(!de_fat_dirent_read(&record_view, volume.bits, &file) &&
                file.kind == DE_FAT_DIRENT_FILE && !file.issues && !file.dot,
            "fat_content_record");
    require(integer(node, "file_bytes") == file.file_bytes &&
                integer(node, "cluster") == file.cluster &&
                integer(node, "raw_cluster") == file.raw_cluster &&
                integer(node, "issues") == file.issues &&
                integer(node, "attributes") == file.attributes,
            "fat_content_record");
    const auto record_offset = integer(node, "volume_record_offset");
    require(add(record_offset, 32) <= native(volume.volume_bytes) &&
                integer(node, "source_record_offset") == add(expected.volume_offset, record_offset),
            "fat_content_record");
    const auto &extents = array(node, "extents", 1024);
    const auto &cells = array(node, "cells", 1024);
    require(extents.size() == cells.size() && boolean(node, "chain_complete"), "fat_content_chain");
    if (extents.empty()) {
        text(node, "chain", "empty");
        require(!file.cluster && !file.file_bytes, "fat_content_chain");
    } else {
        text(node, "chain", "end");
        require(file.cluster >= 2, "fat_content_chain");
    }
    FatContentMap out;
    out.binding_ = expected;
    out.node_ = node_id;
    out.file_bytes_ = file.file_bytes;
    out.tree_complete_ = boolean(observation, "selected_tree_complete");
    out.metadata_consistent_ = boolean(observation, "observed_metadata_consistent");
    std::set<std::uint32_t> seen;
    std::uint64_t logical = 0;
    auto cluster = file.cluster;
    for (std::size_t i = 0; i < extents.size(); ++i) {
        const auto &extent = extents[i];
        const auto &cell = cells[i];
        require(cluster >= 2 && cluster <= volume.cluster_count + 1 &&
                    seen.insert(cluster).second && integer(extent, "cluster") == cluster &&
                    integer(cell, "index") == cluster,
                "fat_content_chain");
        const auto start =
            add(native(volume.data_offset_bytes), multiply(cluster - 2, volume.cluster_bytes));
        const auto source = add(expected.volume_offset, start);
        const auto content =
            logical < file.file_bytes
                ? std::min<std::uint64_t>(volume.cluster_bytes, file.file_bytes - logical)
                : 0;
        require(add(start, volume.cluster_bytes) <= native(volume.volume_bytes) &&
                    add(source, volume.cluster_bytes) <= expected.source_bytes &&
                    integer(extent, "volume_offset") == start &&
                    integer(extent, "source_offset") == source &&
                    integer(extent, "file_offset") == logical &&
                    integer(extent, "allocated_bytes") == volume.cluster_bytes &&
                    integer(extent, "content_bytes") == content,
                "fat_content_extent");
        const auto &variants = array(cell, "copies", 16);
        require(variants.size() == volume.fat_count, "fat_content_copy_coverage");
        std::set<std::uint32_t> copies;
        de_fat_entry selected{};
        bool have_selected = false;
        for (const auto &variant : variants) {
            require(variant.kind == V::Kind::array && variant.items.size() == 2,
                    "fat_content_copy_coverage");
            const auto copy = integer(variant.items[0]);
            require(copy < volume.fat_count &&
                        copies.insert(static_cast<std::uint32_t>(copy)).second,
                    "fat_content_copy_coverage");
            const auto entry = decode_cell(integer(variant.items[1]), cluster, volume);
            require(entry.value == integer(cell, "value") &&
                        static_cast<std::uint64_t>(entry.kind) == integer(cell, "kind"),
                    "fat_content_copy_disagreement");
            if (copy == expected.fat_copy) {
                selected = entry;
                have_selected = true;
            }
        }
        require(have_selected, "fat_content_copy_coverage");
        require((i + 1 == extents.size() && selected.kind == DE_FAT_ENTRY_END) ||
                    (i + 1 < extents.size() && selected.kind == DE_FAT_ENTRY_NEXT),
                "fat_content_chain");
        if (content)
            out.extents_.push_back({source, logical, content});
        logical = add(logical, volume.cluster_bytes);
        cluster = selected.value;
    }
    require(logical == integer(node, "allocated_bytes") && logical >= file.file_bytes,
            "fat_content_chain");
    const auto needed =
        file.file_bytes / volume.cluster_bytes + (file.file_bytes % volume.cluster_bytes ? 1u : 0u);
    out.excess_allocation_ = extents.size() > needed;
    const auto &crosses = array(observation, "cross_links", 4096);
    std::set<std::uint64_t> cross_clusters;
    for (const auto &cross : crosses) {
        const auto c = integer(cross, "cluster");
        require(c >= 2 && c <= volume.cluster_count + 1 && cross_clusters.insert(c).second);
        const auto &owners = array(cross, "owners", 128);
        require(owners.size() >= 2);
        std::set<std::uint64_t> ids;
        for (const auto &owner : owners) {
            const auto id = integer(owner);
            require(id < nodes.size() && ids.insert(id).second);
            if (id == node_id) {
                require(seen.count(static_cast<std::uint32_t>(c)) != 0);
                out.cross_link_ = true;
            }
        }
    }
    bool named_cross = false;
    for (const auto &diagnostic : array(node, "diagnostics", 128)) {
        require(diagnostic.kind == V::Kind::string && diagnostic.text.size() <= 128);
        named_cross = named_cross || diagnostic.text == "fat_cross_link";
    }
    require(named_cross == out.cross_link_);
    return out;
}

json::Value FatContentMap::read(std::uint64_t offset, std::size_t count, const RegionReader &reader,
                                FatContentLimits limits) const {
    require(count && count <= limits.bytes && limits.bytes && limits.bytes <= 196608 &&
                limits.read_requests && limits.read_requests <= 512 && limits.read_chunk &&
                limits.read_chunk <= 4096,
            "fat_content_limits");
    require(offset <= file_bytes_, "fat_content_range");
    const auto wanted = std::min<std::uint64_t>(count, file_bytes_ - offset);
    struct Piece {
        std::uint64_t source, file;
        std::size_t bytes;
    };
    std::vector<Piece> pieces;
    pieces.reserve(limits.read_requests);
    const auto end = add(offset, wanted);
    for (const auto &extent : extents_) {
        auto begin = std::max(offset, extent.file);
        const auto finish = std::min(end, add(extent.file, extent.content));
        while (begin < finish) {
            require(pieces.size() < limits.read_requests, "fat_content_read_budget");
            const auto bytes = static_cast<std::size_t>(
                std::min<std::uint64_t>(limits.read_chunk, finish - begin));
            pieces.push_back({add(extent.source, begin - extent.file), begin, bytes});
            begin = add(begin, bytes);
        }
    }
    require(!wanted || reader, "fat_content_reader_required");
    Bytes bytes;
    bytes.reserve(static_cast<std::size_t>(wanted));
    auto receipts = V::array();
    receipts.items.reserve(pieces.size());
    std::string outcome = "complete";
    auto capacity = portable(binding_.source_bytes);
    de_block_space space{};
    require(
        !de_space_init(binding_.source_id.data(), binding_.source_id.size(), &capacity, 1, &space));
    for (const auto &piece : pieces) {
        auto start = portable(piece.source), length = portable(piece.bytes);
        de_block_extent extent{};
        de_byte_extent request{};
        require(!de_extent_make(&space, &start, &length, &extent) &&
                    !de_extent_to_bytes(&extent, &request),
                "fat_content_extent");
        de_view view{};
        try {
            view = reader(request);
        } catch (...) {
            outcome = "reader_error";
        }
        if (outcome == "complete" && ((view.size && !view.data) || view.size > piece.bytes))
            outcome = "invalid_reader_view";
        const auto returned = outcome == "complete" ? view.size : 0;
        const auto reported = outcome == "reader_error" ? V{} : exact(view.size);
        if (returned)
            bytes.insert(bytes.end(), view.data, view.data + returned);
        if (outcome == "complete" && returned < piece.bytes)
            outcome = "short_read";
        receipts.items.push_back(V::object()
                                     .put("source_offset", exact(piece.source))
                                     .put("file_offset", exact(piece.file))
                                     .put("requested_bytes", exact(piece.bytes))
                                     .put("reported_bytes", reported)
                                     .put("returned_bytes", exact(returned))
                                     .put("outcome", V::string(outcome)));
        if (outcome != "complete")
            break;
    }
    require(outcome != "complete" || bytes.size() == wanted, "fat_content_internal");
    return V::object()
        .put("schema", V::string("org.disked.fat-content-window/1"))
        .put("scope", V::string("supplied-reader-file-content"))
        .put("source_id", V::string(binding_.source_id))
        .put("capture_epoch", exact(binding_.epoch))
        .put("node_id", exact(node_))
        .put("file_bytes", exact(file_bytes_))
        .put("byte_offset", exact(offset))
        .put("requested_bytes", exact(count))
        .put("available_bytes", exact(wanted))
        .put("returned_bytes", exact(bytes.size()))
        .put("next_offset", exact(add(offset, bytes.size())))
        .put("outcome", V::string(outcome))
        .put("eof", V::boolean_value(offset + bytes.size() == file_bytes_))
        .put("encoding", V::string("hex"))
        .put("data", V::string(hex(bytes)))
        .put("reads", std::move(receipts))
        .put("selected_tree_complete", V::boolean_value(tree_complete_))
        .put("observed_metadata_consistent", V::boolean_value(metadata_consistent_))
        .put("known_cross_link", V::boolean_value(cross_link_))
        .put("excess_allocation", V::boolean_value(excess_allocation_))
        .put("source_freshness_verified", V::boolean_value(false))
        .put("filesystem_health_qualified", V::boolean_value(false))
        .put("product_dispatch_admitted", V::boolean_value(false))
        .put("authorizes_effects", V::boolean_value(false));
}
} // namespace disked
