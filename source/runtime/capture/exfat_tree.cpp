#include "exfat_tree.h"
#include "exfat_namespace.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <deque>
#include <limits>
#include <set>
#include <stdexcept>

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
        stop("exfat_tree_internal");
}
std::uint64_t native(const de_u64 &value) {
    char text[21];
    checked(de_u64_format(&value, text, sizeof(text)));
    return std::stoull(text);
}
de_u64 portable(std::uint64_t value) {
    de_u64 out{};
    const auto text = std::to_string(value);
    checked(de_u64_parse(text.data(), text.size(), &out));
    return out;
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    if (b > std::numeric_limits<std::uint64_t>::max() - a)
        stop("exfat_tree_overflow");
    return a + b;
}
std::uint64_t mul(std::uint64_t a, std::uint64_t b) {
    if (a && b > std::numeric_limits<std::uint64_t>::max() / a)
        stop("exfat_tree_overflow");
    return a * b;
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const Bytes &bytes) {
    const char digits[] = "0123456789abcdef";
    std::string text;
    text.reserve(bytes.size() * 2);
    for (auto byte : bytes) {
        text += digits[byte >> 4];
        text += digits[byte & 15];
    }
    return text;
}
Bytes unhex(const std::string &text) {
    const auto digit = [](char c) -> unsigned {
        if (c >= '0' && c <= '9')
            return static_cast<unsigned>(c - '0');
        if (c >= 'a' && c <= 'f')
            return static_cast<unsigned>(c - 'a' + 10);
        stop("exfat_tree_internal");
    };
    if (text.size() % 2)
        stop("exfat_tree_internal");
    Bytes bytes;
    bytes.reserve(text.size() / 2);
    for (std::size_t i = 0; i < text.size(); i += 2)
        bytes.push_back(static_cast<unsigned char>(digit(text[i]) * 16 + digit(text[i + 1])));
    return bytes;
}
std::string digest(const Bytes &bytes) {
    unsigned char value[32];
    sha256(bytes.data(), bytes.size(), value);
    return "sha256:" + hex(Bytes(value, value + 32));
}
json::Limits encoding(std::size_t bytes) {
    json::Limits limits;
    limits.bytes = bytes;
    limits.string_bytes = bytes;
    limits.values = 1048576;
    limits.depth = 64;
    return limits;
}
struct Directory {
    std::size_t id = 0, parent = 0, entry = 0, depth = 0;
    std::vector<std::uint32_t> clusters;
    bool root = false;
};
class Tree {
    const ExfatCaptureRequest request_;
    const ExfatTreePort &port_;
    const ExfatTreeLimits &limits_;
    de_block_space space_{};
    std::unique_ptr<ExfatVolumeCapture> capture_;
    std::unique_ptr<ExfatUpcaseMap> map_;
    std::set<std::uint32_t> occupied_;
    std::vector<ExfatCapturedRegion> regions_;
    ExfatNamespaceDirectory pending_;
    bool collecting_ = false;
    std::size_t reads_ = 0, read_bytes_ = 0, copied_ = 0, content_ = 0, records_ = 0;
    std::size_t next_directory_ = 1, directories_ = 0, rereads_ = 0;
    V directory_rows_ = V::array(), entries_ = V::array(), diagnostics_ = V::array();
    const char *reader_failure_ = nullptr;
    bool complete_ = true, reread_equal_ = false;

    void diagnostic(const char *code) {
        complete_ = false;
        for (const auto &row : diagnostics_.items)
            if (row.text == code)
                return;
        diagnostics_.items.push_back(V::string(code));
    }
    void retain(std::size_t n) {
        if (n > limits_.retained_bytes - copied_)
            stop("exfat_tree_retained_budget");
        copied_ += n;
    }
    bool applicable() const {
        try {
            return port_.applicable(request_);
        } catch (...) {
            return false;
        }
    }
    de_view fetch(const de_byte_extent &extent) {
        const auto start = native(extent.start), end = native(extent.end);
        const auto fail = [&](const char *code) -> de_view {
            reader_failure_ = code;
            stop(code);
        };
        if (!applicable())
            return fail("exfat_tree_inapplicable");
        if (end <= start || start < request_.volume_offset ||
            end > add(request_.volume_offset, request_.volume_bytes))
            return fail("exfat_tree_read_bounds");
        const auto length = end - start;
        if (reads_ == limits_.read_requests || length > limits_.read_bytes - read_bytes_)
            return fail("exfat_tree_read_budget");
        ++reads_;
        read_bytes_ += static_cast<std::size_t>(length);
        de_view view{};
        try {
            view = port_.read(extent);
        } catch (...) {
            return fail("exfat_tree_reader_failure");
        }
        if (!view.data || view.size != length)
            return fail("exfat_tree_read_length");
        return view;
    }
    de_view fetch(std::uint64_t start, std::size_t length) {
        de_block_extent blocks{};
        de_byte_extent extent{};
        const auto offset = portable(start), bytes = portable(length);
        checked(de_extent_make(&space_, &offset, &bytes, &blocks));
        checked(de_extent_to_bytes(&blocks, &extent));
        return fetch(extent);
    }
    void agree(const ExfatCapturedRegion &prior, std::uint64_t start, const Bytes &bytes) {
        const auto begin = std::max(prior.start, start);
        const auto end = std::min(add(prior.start, prior.bytes.size()), add(start, bytes.size()));
        if (begin < end &&
            !std::equal(bytes.begin() + static_cast<std::size_t>(begin - start),
                        bytes.begin() + static_cast<std::size_t>(end - start),
                        prior.bytes.begin() + static_cast<std::size_t>(begin - prior.start)))
            stop("exfat_tree_source_changed");
    }
    Bytes read(std::uint64_t start, std::size_t length) {
        retain(length * 2);
        const auto view = fetch(start, length);
        Bytes bytes(view.data, view.data + length);
        for (const auto &prior : capture_->regions())
            agree(prior, start, bytes);
        for (const auto &prior : regions_)
            agree(prior, start, bytes);
        regions_.push_back(ExfatCapturedRegion{start, bytes});
        return bytes;
    }
    std::uint64_t cluster_offset(std::uint32_t cluster) const {
        const auto &boot = capture_->boot();
        return add(request_.volume_offset,
                   add(native(boot.heap_offset_bytes), mul(cluster - 2, boot.cluster_bytes)));
    }
    void claim(std::uint32_t cluster) {
        const auto &boot = capture_->boot();
        if (cluster < 2 || cluster > boot.cluster_count + 1)
            stop("exfat_tree_cluster_bounds");
        if (occupied_.size() == limits_.clusters)
            stop("exfat_tree_cluster_budget");
        if (!occupied_.insert(cluster).second)
            stop("exfat_tree_crosslink");
        const auto bit = static_cast<std::uint64_t>(cluster) - 2;
        const auto &bitmap = capture_->bitmap();
        if (bit / 8 >= bitmap.size())
            stop("exfat_tree_internal");
        if (!(bitmap[static_cast<std::size_t>(bit / 8)] & (1U << (bit % 8))))
            stop("exfat_tree_cluster_available");
    }
    std::vector<std::uint32_t> chain(const de_exfat_file_set &set) {
        const auto &boot = capture_->boot();
        const auto length = native(set.data_length);
        const auto count = length / boot.cluster_bytes + (length % boot.cluster_bytes != 0);
        std::vector<std::uint32_t> clusters;
        if (!count) {
            if (set.first_cluster)
                stop("exfat_tree_empty_allocation");
            return clusters;
        }
        auto cluster = static_cast<std::uint32_t>(set.first_cluster);
        std::set<std::uint32_t> seen;
        for (std::uint64_t i = 0; i < count; ++i) {
            if (!seen.insert(cluster).second)
                stop("exfat_tree_chain_cycle");
            claim(cluster);
            clusters.push_back(cluster);
            if (set.stream_flags & 2) {
                if (i + 1 < count)
                    ++cluster;
                continue;
            }
            const auto table = add(mul(boot.fat_offset, boot.sector_bytes),
                                   mul(boot.active_fat, native(boot.fat_bytes)));
            const auto bytes = read(add(request_.volume_offset, add(table, mul(cluster, 4))), 4);
            const de_view view{bytes.data(), bytes.size()};
            de_exfat_cell cell{};
            checked(de_exfat_cell_read(&view, boot.cluster_count, cluster, &cell));
            if (i + 1 == count) {
                if (cell.kind == DE_EXFAT_CELL_NEXT &&
                    seen.count(static_cast<std::uint32_t>(cell.value)))
                    stop("exfat_tree_chain_cycle");
                if (cell.kind != DE_EXFAT_CELL_END)
                    stop("exfat_tree_chain_length");
            } else {
                if (cell.kind != DE_EXFAT_CELL_NEXT)
                    stop("exfat_tree_chain_length");
                cluster = static_cast<std::uint32_t>(cell.value);
            }
        }
        return clusters;
    }
    ExfatNamespaceDirectory collect(const Directory &directory) {
        pending_ = ExfatNamespaceDirectory{};
        collecting_ = true;
        auto &out = pending_;
        out.id = directory.id;
        out.root = directory.root;
        out.extent_complete = false;
        if (directory.root) {
            for (const auto &row : capture_->report().fields.at("root_records").items) {
                const auto raw = unhex(row.fields.at("raw").text);
                ExfatDirectoryRecord record;
                record.source_offset = std::stoull(row.fields.at("source_offset").text);
                std::copy(raw.begin(), raw.end(), record.bytes.begin());
                out.records.push_back(record);
            }
            if (out.records.size() > limits_.records - records_)
                stop("exfat_tree_record_budget");
            records_ += out.records.size();
            out.extent_complete = true;
            collecting_ = false;
            return std::move(out);
        }
        for (auto cluster : directory.clusters) {
            for (std::size_t at = 0; at < capture_->boot().cluster_bytes;) {
                const auto n = std::min<std::size_t>(8192, capture_->boot().cluster_bytes - at);
                const auto offset = add(cluster_offset(cluster), at);
                const auto bytes = read(offset, n);
                for (std::size_t i = 0; i < bytes.size(); i += 32) {
                    if (records_ == limits_.records)
                        stop("exfat_tree_record_budget");
                    retain(32);
                    ++records_;
                    ExfatDirectoryRecord record;
                    record.source_offset = add(offset, i);
                    std::copy_n(bytes.begin() + i, 32, record.bytes.begin());
                    out.records.push_back(record);
                    if (!record.bytes[0]) {
                        out.extent_complete = true;
                        collecting_ = false;
                        return std::move(out);
                    }
                }
                at += n;
            }
        }
        out.extent_complete = true;
        collecting_ = false;
        return std::move(out);
    }
    void content(V &row, const de_exfat_file_set &set, const std::vector<std::uint32_t> &clusters) {
        const auto length = native(set.data_length), valid = native(set.valid_data_length);
        if (length > limits_.content_bytes - content_)
            stop("exfat_tree_content_budget");
        const auto size = static_cast<std::size_t>(length);
        retain(size);
        content_ += size;
        Bytes bytes(size, 0);
        std::uint64_t copied = 0;
        for (auto cluster : clusters) {
            if (copied == valid)
                break;
            const auto n = static_cast<std::size_t>(
                std::min<std::uint64_t>(capture_->boot().cluster_bytes, valid - copied));
            for (std::size_t at = 0; at < n;) {
                const auto amount = std::min<std::size_t>(8192, n - at);
                const auto part = read(add(cluster_offset(cluster), at), amount);
                std::copy(part.begin(), part.end(),
                          bytes.begin() + static_cast<std::size_t>(copied) + at);
                at += amount;
            }
            copied += n;
        }
        row.put("content_complete", V::boolean_value(true))
            .put("source_data_bytes", exact(valid))
            .put("defined_zero_bytes", exact(length - valid))
            .put("content_hex", V::string(hex(bytes)))
            .put("content_sha256", V::string(digest(bytes)));
    }
    void walk() {
        Directory root;
        root.root = true;
        std::deque<Directory> queue{root};
        const auto &boot = capture_->boot();
        while (!queue.empty()) {
            if (directories_ == limits_.directories)
                stop("exfat_tree_directory_budget");
            Directory current = std::move(queue.front());
            queue.pop_front();
            ++directories_;
            auto records = collect(current);
            auto names = observe_exfat_namespace({records}, *map_, {}, boot.cluster_count,
                                                 boot.sector_shift + boot.cluster_shift);
            const auto *dirs = names.find("directories");
            if (!dirs || dirs->items.empty() ||
                !dirs->items.front().fields.at("model_complete").boolean)
                diagnostic("exfat_tree_namespace_incomplete");
            if (const auto *findings = names.find("findings"))
                for (const auto &finding : findings->items)
                    if (finding.fields.at("code").text == "exfat_name_collision")
                        diagnostic("exfat_tree_name_collision");
            directory_rows_.items.push_back(V::object()
                                                .put("id", exact(current.id))
                                                .put("parent_id", exact(current.parent))
                                                .put("parent_entry", exact(current.entry))
                                                .put("depth", exact(current.depth))
                                                .put("namespace", names));
            const auto *named = names.find("entries");
            if (!named)
                continue;
            for (const auto &entry : named->items) {
                auto row = V::object()
                               .put("directory_id", exact(current.id))
                               .put("entry", entry)
                               .put("stream_complete", V::boolean_value(false))
                               .put("content_complete", V::boolean_value(false));
                entries_.items.push_back(std::move(row));
                auto &result = entries_.items.back();
                const auto raw = unhex(entry.fields.at("raw_set_hex").text);
                const de_view view{raw.data(), raw.size()};
                de_exfat_file_set set{};
                checked(de_exfat_file_set_read(&view, boot.cluster_count,
                                               boot.sector_shift + boot.cluster_shift, 8192, &set));
                if (!set.stream_valid) {
                    diagnostic("exfat_tree_invalid_stream");
                    continue;
                }
                const auto clusters = chain(set);
                auto cells = V::array();
                for (auto cluster : clusters)
                    cells.items.push_back(exact(cluster));
                result.put("clusters", std::move(cells))
                    .put("stream_complete", V::boolean_value(true))
                    .put("no_fat_chain", V::boolean_value((set.stream_flags & 2) != 0));
                if (set.attributes & 16) {
                    if (current.depth == limits_.depth)
                        stop("exfat_tree_depth_budget");
                    if (next_directory_ == limits_.directories)
                        stop("exfat_tree_directory_budget");
                    Directory child;
                    child.id = next_directory_++;
                    child.parent = current.id;
                    child.entry = static_cast<std::size_t>(std::stoull(entry.fields.at("id").text));
                    child.depth = current.depth + 1;
                    child.clusters = clusters;
                    result.put("child_directory_id", exact(child.id));
                    queue.push_back(std::move(child));
                } else
                    content(result, set, clusters);
            }
        }
    }
    void reread() {
        const auto verify = [&](const ExfatCapturedRegion &region) {
            const auto view = fetch(region.start, region.bytes.size());
            if (!std::equal(region.bytes.begin(), region.bytes.end(), view.data))
                stop("exfat_tree_source_changed");
            ++rereads_;
        };
        for (const auto &region : capture_->regions())
            verify(region);
        for (const auto &region : regions_)
            verify(region);
        if (!applicable())
            stop("exfat_tree_inapplicable");
        reread_equal_ = true;
    }

  public:
    Tree(const ExfatCaptureRequest &request, const ExfatTreePort &port,
         const ExfatTreeLimits &limits)
        : request_(request), port_(port), limits_(limits) {
        validate_exfat_capture_request(request);
        if (!port.read || !port.applicable || !limits.directories || limits.directories > 256 ||
            !limits.depth || limits.depth > 32 || !limits.clusters || limits.clusters > 4096 ||
            !limits.records || limits.records > 4096 || !limits.read_requests ||
            limits.read_requests > 16384 || !limits.read_bytes || limits.read_bytes > 8388608 ||
            !limits.retained_bytes || limits.retained_bytes > 8388608 || !limits.content_bytes ||
            limits.content_bytes > 1048576 || limits.output_bytes < 65536 ||
            limits.output_bytes > 4194304)
            throw std::invalid_argument("exfat_tree_inputs");
        const auto length = portable(request.source_bytes);
        checked(de_space_from_bytes(request.source_id.data(), request.source_id.size(), &length, 1,
                                    &space_));
    }
    V run() {
        try {
            if (!applicable())
                stop("exfat_tree_inapplicable");
            RegionReader reader = [this](const de_byte_extent &extent) { return fetch(extent); };
            auto root_request = request_;
            root_request.limits.records = std::min(root_request.limits.records, limits_.records);
            root_request.limits.clusters = std::min(root_request.limits.clusters, limits_.clusters);
            root_request.limits.retained_bytes =
                std::min(root_request.limits.retained_bytes, limits_.retained_bytes);
            root_request.limits.read_bytes =
                std::min(root_request.limits.read_bytes, limits_.read_bytes);
            root_request.limits.read_requests =
                std::min(root_request.limits.read_requests, limits_.read_requests);
            capture_.reset(new ExfatVolumeCapture(ExfatVolumeCapture::read(root_request, reader)));
            retain(static_cast<std::size_t>(
                std::stoull(capture_->report().fields.at("retained_bytes").text)));
            if (!capture_->valid()) {
                for (const auto &code : capture_->report().fields.at("diagnostics").items)
                    diagnostic(code.text.c_str());
                stop(reader_failure_ ? reader_failure_ : "exfat_tree_root_incomplete");
            }
            retain(786432);
            map_.reset(new ExfatUpcaseMap(ExfatUpcaseMap::read(
                capture_->upcase(), capture_->upcase_checksum(), request_.upcase_format)));
            if (!map_->valid())
                stop("exfat_tree_map_incomplete");
            occupied_ = capture_->system_clusters();
            if (occupied_.size() > limits_.clusters)
                stop("exfat_tree_cluster_budget");
            // Every declared bitmap is a reserved system stream, even though
            // only the active bitmap supplies the allocation interpretation.
            for (const auto &descriptor :
                 capture_->report().fields.at("bitmap_descriptors").items) {
                if (std::stoull(descriptor.fields.at("identifier").text) ==
                    capture_->boot().active_fat)
                    continue;
                de_exfat_file_set system{};
                system.first_cluster =
                    static_cast<de_u32>(std::stoull(descriptor.fields.at("first_cluster").text));
                system.data_length =
                    portable(std::stoull(descriptor.fields.at("data_length").text));
                system.stream_flags = 1;
                chain(system);
            }
            walk();
            reread();
        } catch (const Stop &failure) {
            diagnostic(failure.code);
        }
        auto partial = V{};
        if (collecting_) {
            auto records = V::array();
            for (const auto &record : pending_.records)
                records.items.push_back(
                    V::object()
                        .put("source_offset", exact(record.source_offset))
                        .put("raw_hex",
                             V::string(hex(Bytes(record.bytes.begin(), record.bytes.end())))));
            partial = V::object()
                          .put("directory_id", exact(pending_.id))
                          .put("records", std::move(records))
                          .put("complete", V::boolean_value(false));
        }
        auto out = V::object()
                       .put("schema", V::string("org.disked.exfat-tree/1"))
                       .put("scope", V::string("bounded-supplied-reader-tree"))
                       .put("complete", V::boolean_value(complete_ && reread_equal_))
                       .put("reread_equal", V::boolean_value(reread_equal_))
                       .put("rereads", exact(rereads_))
                       .put("root", capture_ ? capture_->report() : V{})
                       .put("directories", directory_rows_)
                       .put("entries", entries_)
                       .put("partial_directory", std::move(partial))
                       .put("diagnostics", diagnostics_)
                       .put("read_requests", exact(reads_))
                       .put("read_bytes", exact(read_bytes_))
                       .put("copied_bytes", exact(copied_))
                       .put("content_bytes", exact(content_))
                       .put("records", exact(records_))
                       .put("clusters_claimed", exact(occupied_.size()))
                       .put("atomic_snapshot", V::boolean_value(false))
                       .put("current_source_authority", V::boolean_value(false))
                       .put("authorizes_effects", V::boolean_value(false));
        try {
            json::dump(out, encoding(limits_.output_bytes));
        } catch (const json::Error &) {
            return V::object()
                .put("schema", V::string("org.disked.exfat-tree/1"))
                .put("scope", V::string("bounded-supplied-reader-tree"))
                .put("complete", V::boolean_value(false))
                .put("diagnostic", V::string("exfat_tree_output_budget"))
                .put("read_requests", exact(reads_))
                .put("read_bytes", exact(read_bytes_))
                .put("authorizes_effects", V::boolean_value(false));
        }
        return out;
    }
};
} // namespace
V observe_exfat_tree(const ExfatCaptureRequest &request, const ExfatTreePort &port,
                     const ExfatTreeLimits &limits) {
    return Tree(request, port, limits).run();
}
} // namespace disked
