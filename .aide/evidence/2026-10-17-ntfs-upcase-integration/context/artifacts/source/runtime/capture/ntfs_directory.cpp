#include "ntfs_directory_detail.h"
#include "ntfs_stream.h"
#include "portable/hash/sha256.h"
#include "portable/ntfs/ntfs.h"
#include <set>
#include <stdexcept>
#include <utility>

namespace disked {
void validate_ntfs_directory_request(const NtfsDirectoryRequest &r) {
    validate_ntfs_capture_request(r.capture);
    if (r.reference && !(r.reference >> 48))
        throw std::invalid_argument("ntfs_directory_reference");
    if (!r.limits.entries || r.limits.entries > 4096 || !r.limits.blocks || r.limits.blocks > 128 ||
        !r.limits.bitmap_bytes || r.limits.bitmap_bytes > 65536)
        throw std::invalid_argument("ntfs_directory_limits");
}
namespace ntfs_directory_detail {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
struct Stop {
    const char *code;
};
[[noreturn]] void stop(const char *code) {
    throw Stop{code};
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V flag(bool n) {
    return V::boolean_value(n);
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::logic_error("ntfs_directory_internal");
    return std::stoull(text);
}
de_u64 portable(std::uint64_t n) {
    const auto text = std::to_string(n);
    de_u64 value{};
    if (de_u64_parse(text.data(), text.size(), &value))
        throw std::logic_error("ntfs_directory_internal");
    return value;
}
std::string hex(const unsigned char *p, std::size_t n) {
    const char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(n * 2);
    for (std::size_t i = 0; i < n; ++i) {
        result += digits[p[i] >> 4];
        result += digits[p[i] & 15];
    }
    return result;
}
std::string digest(const unsigned char *p, std::size_t n) {
    const unsigned char empty = 0;
    unsigned char hash[32];
    sha256(n ? p : &empty, n, hash);
    return "sha256:" + hex(hash, sizeof(hash));
}
class Collector {
    struct Child {
        std::uint64_t vbn;
        std::size_t depth;
    };
    const NtfsDirectoryLimits limits_;
    const Geometry geometry_;
    const Port port_;
    V &out_;
    std::vector<Edge> *edges_;
    std::vector<Child> queue_;
    std::set<std::uint64_t> seen_, allocated_;
    std::size_t headers_ = 0, names_ = 0, blocks_ = 0;
    std::size_t leaf_depth_ = 0;
    bool leaf_seen_ = false;
    std::uint32_t child_unit_ = 0;
    void sync() {
        out_.put("header_count", exact(headers_))
            .put("name_count", exact(names_))
            .put("queued_blocks", exact(queue_.size()))
            .put("observed_blocks", exact(blocks_))
            .put("leaf_depth", leaf_seen_ ? exact(leaf_depth_) : V{});
    }
    void charge(const V &v) {
        auto limits = json::Limits{};
        limits.bytes = limits.string_bytes = 1048576;
        limits.values = 262144;
        port_.charge(json::dump(v, limits).size() + 2);
    }
    void describe(const NtfsJoinedStream &stream) {
        auto value = V::object()
                         .put("type", exact(stream.type))
                         .put("name_hex", V::string(hex(stream.name.data(), stream.name.size())))
                         .put("resident", flag(stream.resident))
                         .put("allocated_bytes", exact(stream.allocated_bytes))
                         .put("data_bytes", exact(stream.data_bytes))
                         .put("initialized_bytes", exact(stream.initialized_bytes))
                         .put("runs", V::array())
                         .put("parts", V::array());
        charge(value);
        out_.fields.at("streams").items.push_back(std::move(value));
        auto &stored = out_.fields.at("streams").items.back();
        for (const auto &run : stream.runs) {
            auto row = V::object()
                           .put("vcn", exact(run.vcn))
                           .put("clusters", exact(run.clusters))
                           .put("lcn", exact(run.lcn));
            charge(row);
            stored.fields.at("runs").items.push_back(std::move(row));
        }
        for (const auto &part : stream.parts) {
            auto row = V::object()
                           .put("reference", exact(part.reference))
                           .put("instance", exact(part.instance))
                           .put("lowest_vcn", exact(part.lowest_vcn))
                           .put("highest_vcn", exact(part.highest_vcn));
            charge(row);
            stored.fields.at("parts").items.push_back(std::move(row));
        }
    }
    void enqueue(std::uint64_t vbn, std::size_t depth) {
        if (seen_.count(vbn))
            stop("ntfs_directory_child_repeated");
        if (queue_.size() == limits_.blocks)
            stop("ntfs_directory_block_budget");
        seen_.insert(vbn);
        queue_.push_back(Child{vbn, depth});
        sync();
    }
    void entries(de_ntfs_index_cursor &cursor, bool root, std::uint64_t vbn, std::size_t depth) {
        de_ntfs_index_entry entry{};
        for (;;) {
            const auto before = cursor.count;
            const auto status = de_ntfs_index_next(&cursor, &entry);
            if (status == DE_EMPTY)
                break;
            if (status != DE_OK)
                throw std::logic_error("ntfs_directory_cursor");
            headers_ += cursor.count - before;
            sync();
            auto row = V::object()
                           .put("header_number", exact(headers_))
                           .put("index_vbn", root ? V{} : exact(vbn))
                           .put("present", flag(entry.present != 0))
                           .put("end_marker", flag(entry.end_marker != 0))
                           .put("has_child", flag(entry.has_child != 0))
                           .put("issues", exact(entry.issues))
                           .put("envelope_valid", flag(entry.envelope_valid != 0));
            bool parent_matches = true;
            if (entry.envelope_valid) {
                row.put("child_vbn", entry.has_child ? exact(native(entry.child_vbn)) : V{});
                if (!entry.end_marker) {
                    parent_matches = native(entry.filename.parent_reference) == geometry_.reference;
                    row.put("reference", exact(native(entry.segment_reference)))
                        .put("parent_reference", exact(native(entry.filename.parent_reference)))
                        .put("parent_matches", flag(parent_matches))
                        .put("namespace", exact(entry.filename.namespace_code))
                        .put("name_hex",
                             V::string(hex(entry.filename.name.data, entry.filename.name.size)))
                        .put("key_sha256", V::string(digest(entry.key.data, entry.key.size)));
                    ++names_;
                    sync();
                }
            }
            charge(row);
            out_.fields.at("entries").items.push_back(std::move(row));
            if (!entry.envelope_valid)
                stop(entry.issues & DE_NTFS_INDEX_BUDGET ? "ntfs_directory_entry_budget"
                                                         : "ntfs_directory_entry");
            if (!parent_matches)
                stop("ntfs_directory_parent_reference");
            if (edges_ && !entry.end_marker)
                edges_->push_back(Edge{headers_, native(entry.segment_reference),
                                       native(entry.filename.parent_reference),
                                       entry.filename.namespace_code,
                                       Bytes(entry.filename.name.data,
                                             entry.filename.name.data + entry.filename.name.size)});
            if (entry.has_child)
                enqueue(native(entry.child_vbn), depth + 1);
        }
        if (!cursor.terminated || cursor.issues)
            stop("ntfs_directory_entry");
        if (!cursor.has_children) {
            if (leaf_seen_ && leaf_depth_ != depth)
                stop("ntfs_directory_leaf_depth");
            leaf_seen_ = true;
            leaf_depth_ = depth;
            sync();
        }
    }
    void bitmap(const NtfsJoinedStream &stream, const NtfsJoinedStream &allocation) {
        if (stream.data_bytes > limits_.bitmap_bytes)
            stop("ntfs_directory_bitmap_budget");
        if (stream.initialized_bytes != stream.data_bytes)
            stop("ntfs_directory_bitmap_sizes");
        if (allocation.resident || allocation.data_bytes % geometry_.index_bytes)
            stop("ntfs_directory_allocation_sizes");
        const auto count = allocation.data_bytes / geometry_.index_bytes;
        if (count / 8 + (count % 8 ? 1 : 0) > stream.data_bytes)
            stop("ntfs_directory_bitmap_capacity");
        const auto bytes = stream.resident
                               ? stream.value
                               : port_.read(stream, 0, static_cast<std::size_t>(stream.data_bytes));
        if (bytes.size() != stream.data_bytes)
            throw std::logic_error("ntfs_directory_bitmap_read");
        auto value = V::object()
                         .put("bytes", exact(bytes.size()))
                         .put("sha256", V::string(digest(bytes.data(), bytes.size())))
                         .put("allocation_blocks", exact(count))
                         .put("set_bits", exact(0));
        charge(value);
        out_.put("bitmap", std::move(value));
        for (std::size_t i = 0; i < bytes.size(); ++i)
            for (unsigned bit = 0; bit < 8; ++bit)
                if (bytes[i] & (1U << bit)) {
                    const auto ordinal = static_cast<std::uint64_t>(i) * 8 + bit;
                    if (ordinal >= count)
                        stop("ntfs_directory_bitmap_range");
                    if (allocated_.size() == limits_.blocks)
                        stop("ntfs_directory_block_budget");
                    allocated_.insert(ordinal);
                    out_.fields.at("bitmap").put("set_bits", exact(allocated_.size()));
                }
        out_.put("bitmap_complete", flag(true));
    }
    void run() {
        const auto root = port_.stream(0x90);
        if (!root)
            stop("ntfs_directory_root_missing");
        describe(*root);
        if (!root->resident)
            stop("ntfs_directory_root_form");
        const de_view value{root->value.data(), root->value.size()};
        de_ntfs_index_root header{};
        de_ntfs_index_cursor cursor{};
        if (de_ntfs_index_root_begin(&value, geometry_.major, geometry_.minor,
                                     geometry_.cluster_bytes, geometry_.index_bytes,
                                     static_cast<unsigned>(limits_.entries), &header, &cursor))
            throw std::logic_error("ntfs_directory_geometry");
        auto fact = V::object()
                        .put("value_bytes", exact(value.size))
                        .put("value_sha256", V::string(digest(value.data, value.size)))
                        .put("issues", exact(header.issues))
                        .put("envelope_valid", flag(header.envelope_valid != 0))
                        .put("directory_profile", flag(header.directory_profile != 0))
                        .put("child_unit_bytes", exact(header.child_unit_bytes))
                        .put("has_children", flag((header.flags & 1) != 0));
        charge(fact);
        out_.put("root", std::move(fact));
        if (!header.directory_profile)
            stop("ntfs_directory_root_header");
        child_unit_ = header.child_unit_bytes;
        entries(cursor, true, 0, 0);
        if (headers_ == limits_.entries && !queue_.empty())
            stop("ntfs_directory_entry_budget");
        const auto allocation = port_.stream(0xa0);
        if (allocation)
            describe(*allocation);
        const auto bits = port_.stream(0xb0);
        if (bits)
            describe(*bits);
        if (static_cast<bool>(allocation) != static_cast<bool>(bits))
            stop("ntfs_directory_stream_pair");
        if (!allocation) {
            if (!queue_.empty())
                stop("ntfs_directory_stream_pair");
            out_.put("bitmap_complete", flag(true));
            return;
        }
        bitmap(*bits, *allocation);
        std::set<std::uint64_t> visited;
        for (std::size_t i = 0; i < queue_.size(); ++i) {
            if (headers_ == limits_.entries)
                stop("ntfs_directory_entry_budget");
            const auto child = queue_[i];
            if (child.vbn > UINT64_MAX / child_unit_)
                stop("ntfs_directory_child_bounds");
            const auto offset = child.vbn * child_unit_;
            if (offset % geometry_.index_bytes || offset > allocation->data_bytes ||
                geometry_.index_bytes > allocation->data_bytes - offset ||
                offset > allocation->initialized_bytes ||
                geometry_.index_bytes > allocation->initialized_bytes - offset)
                stop("ntfs_directory_child_bounds");
            const auto ordinal = offset / geometry_.index_bytes;
            if (!allocated_.count(ordinal))
                stop("ntfs_directory_child_unallocated");
            const auto raw = port_.read(*allocation, offset, geometry_.index_bytes);
            if (raw.size() != geometry_.index_bytes)
                throw std::logic_error("ntfs_directory_block_read");
            const de_view original{raw.data(), raw.size()};
            const auto expected = portable(child.vbn);
            de_ntfs_index_block block{};
            if (de_ntfs_index_block_read(&original, geometry_.major, geometry_.minor,
                                         geometry_.index_bytes, &expected, &block))
                throw std::logic_error("ntfs_directory_block_controls");
            auto item = V::object()
                            .put("vbn", exact(child.vbn))
                            .put("ordinal", exact(ordinal))
                            .put("depth", exact(child.depth))
                            .put("raw_sha256", V::string(digest(raw.data(), raw.size())))
                            .put("issues", exact(block.issues))
                            .put("envelope_valid", flag(block.envelope_valid != 0))
                            .put("fixups_valid", flag(block.fixups_valid != 0))
                            .put("mismatched_tails", exact(block.mismatched_tails));
            charge(item);
            out_.fields.at("blocks").items.push_back(std::move(item));
            ++blocks_;
            sync();
            if (!block.envelope_valid)
                stop("ntfs_directory_block_header");
            Bytes restored(raw.size());
            const de_buffer destination{restored.data(), restored.size()};
            if (de_ntfs_index_block_begin(&original, geometry_.major, geometry_.minor,
                                          geometry_.index_bytes, &expected, &destination,
                                          static_cast<unsigned>(limits_.entries - headers_), &block,
                                          &cursor))
                throw std::logic_error("ntfs_directory_block_restore");
            const auto hash = V::string(digest(restored.data(), restored.size()));
            charge(hash);
            out_.fields.at("blocks").items.back().put("restored_sha256", hash);
            visited.insert(ordinal);
            entries(cursor, false, child.vbn, child.depth);
        }
        if (visited != allocated_)
            stop("ntfs_directory_bitmap_unreachable");
    }

  public:
    Collector(NtfsDirectoryLimits limits, Geometry geometry, Port port, V &out,
              std::vector<Edge> *edges)
        : limits_(limits), geometry_(geometry), port_(std::move(port)), out_(out), edges_(edges) {
    }
    void collect() {
        out_ = V::object()
                   .put("schema", V::string("org.disked.ntfs-index-collection/1"))
                   .put("reference", exact(geometry_.reference))
                   .put("index_complete", flag(false))
                   .put("bitmap_complete", flag(false))
                   .put("diagnostic", V::string(""))
                   .put("namespace_verified", flag(false))
                   .put("collation_verified", flag(false))
                   .put("target_membership_verified", flag(false))
                   .put("cluster_allocation_verified", flag(false))
                   .put("streams", V::array())
                   .put("root", V{})
                   .put("bitmap", V{})
                   .put("blocks", V::array())
                   .put("entries", V::array());
        sync();
        port_.charge(2048);
        try {
            run();
            out_.put("index_complete", flag(true));
        } catch (const Stop &failure) {
            out_.put("diagnostic", V::string(failure.code));
        }
        sync();
    }
};
} // namespace
void collect(NtfsDirectoryLimits limits, Geometry geometry, Port port, V &out,
             std::vector<Edge> *edges) {
    if (!port.stream || !port.read || !port.charge || !limits.entries || limits.entries > 4096 ||
        !limits.blocks || limits.blocks > 128 || !limits.bitmap_bytes ||
        limits.bitmap_bytes > 65536 || !(geometry.reference >> 48) || geometry.major != 3 ||
        geometry.minor > 1 || geometry.cluster_bytes < 512 ||
        geometry.cluster_bytes > DE_NTFS_MAX_CLUSTER ||
        (geometry.cluster_bytes & (geometry.cluster_bytes - 1)) || geometry.index_bytes < 512 ||
        geometry.index_bytes > DE_NTFS_MAX_RECORD ||
        (geometry.index_bytes & (geometry.index_bytes - 1)) || (edges && !edges->empty()))
        throw std::invalid_argument("ntfs_directory_port");
    Collector(limits, geometry, std::move(port), out, edges).collect();
}
} // namespace ntfs_directory_detail
} // namespace disked
