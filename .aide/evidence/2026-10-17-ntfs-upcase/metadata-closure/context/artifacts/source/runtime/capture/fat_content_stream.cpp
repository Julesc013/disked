#include "fat_content_stream.h"
#include "portable/fat/fat.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <limits>
#include <vector>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
struct Yield {};
struct Stop {
    const char *code;
};
void require(bool value, const char *code) {
    if (!value)
        throw FatContentStreamError(code);
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    if (b > UINT64_MAX - a)
        throw Stop{"fat_content_stream_overflow"};
    return a + b;
}
de_u64 portable(std::uint64_t n) {
    de_u64 out{};
    const auto text = std::to_string(n);
    if (de_u64_parse(text.data(), text.size(), &out))
        throw Stop{"fat_content_stream_internal"};
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw Stop{"fat_content_stream_internal"};
    return std::stoull(text);
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const Bytes &bytes) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (auto b : bytes) {
        out += digits[b >> 4];
        out += digits[b & 15];
    }
    return out;
}
std::string hash(const Bytes &bytes) {
    unsigned char out[32];
    sha256(bytes.data(), bytes.size(), out);
    return "sha256:" + hex(Bytes(out, out + sizeof(out)));
}
json::Limits limits() {
    json::Limits l;
    l.bytes = 2097152;
    l.values = 262144;
    l.depth = 24;
    l.string_bytes = 393216;
    return l;
}
std::string digest(const V &page) {
    const auto text = "disked:fat-content-stream-page:1\n" + json::dump(page, limits());
    return hash(Bytes(text.begin(), text.end()));
}
bool same(const FatContentStreamSelection &a, const FatContentStreamSelection &b) {
    const auto &x = a.binding, &y = b.binding;
    return x.source_id == y.source_id && x.capture_id == y.capture_id && x.epoch == y.epoch &&
           x.source_bytes == y.source_bytes && x.volume_offset == y.volume_offset &&
           x.volume_bytes == y.volume_bytes && x.fat_copy == y.fat_copy &&
           a.record_source_offset == b.record_source_offset && a.record == b.record;
}
V selection_value(const FatContentStreamSelection &s) {
    const auto &b = s.binding;
    return V::object()
        .put("source_id", V::string(b.source_id))
        .put("capture_id", V::string(b.capture_id))
        .put("capture_epoch", number(b.epoch))
        .put("source_bytes", number(b.source_bytes))
        .put("volume_offset", number(b.volume_offset))
        .put("volume_bytes", number(b.volume_bytes))
        .put("fat_copy", number(b.fat_copy))
        .put("record_source_offset", number(s.record_source_offset))
        .put("raw_record", V::string(hex(Bytes(s.record.begin(), s.record.end()))));
}
const char *chain_name(int n) {
    switch (n) {
    case DE_FAT_CHAIN_EMPTY:
        return "empty";
    case DE_FAT_CHAIN_END:
        return "end";
    case DE_FAT_CHAIN_FREE:
        return "free";
    case DE_FAT_CHAIN_BAD:
        return "bad";
    case DE_FAT_CHAIN_RESERVED:
        return "reserved";
    case DE_FAT_CHAIN_INVALID_START:
        return "invalid_start";
    case DE_FAT_CHAIN_CYCLE:
        return "cycle";
    case DE_FAT_CHAIN_TRUNCATED:
        return "truncated";
    default:
        return "pending";
    }
}
void validate(const FatContentStreamBudget &b) {
    require(b.bytes && b.bytes <= 196608 && b.reads >= 4 && b.reads <= 512 &&
                b.read_bytes >= 4096 && b.read_bytes <= 1048576 && b.cells && b.cells <= 512 &&
                b.output_bytes <= 2097152 &&
                b.output_bytes >= 16384 + 2 * b.bytes + 256 * b.reads + 512 * b.cells,
            "fat_content_stream_budget");
}
} // namespace
struct FatContentStream::Impl {
    const FatContentStreamSelection selected;
    const FatTraversalPort port;
    const std::size_t bitmap_limit;
    de_block_space space{};
    de_fat_volume volume{};
    de_fat_dirent file{};
    de_fat_walk walk{};
    Bytes boot, bitmap;
    FatContentStreamBudget budget;
    V cells = V::array(), receipts = V::array(), chunks = V::array(), metadata = V::array();
    Bytes data;
    std::size_t reads = 0, read_bytes = 0;
    std::uint64_t position = 0, sequence = 0, cluster_at = 0, cluster_content = 0, cluster_used = 0;
    int stage = 0;
    bool stopped = false, applicable = true, initialized = false, excess = false,
         record_verified = false;
    std::string diagnostic, previous;

    Impl(const FatContentStreamSelection &s, const FatTraversalPort &p, std::size_t maximum)
        : selected(s), port(p), bitmap_limit(maximum) {
        const auto &b = s.binding;
        require(!b.source_id.empty() && b.source_id.size() <= 128 && !b.capture_id.empty() &&
                    b.capture_id.size() <= 256 && json::valid_utf8(b.source_id) &&
                    json::valid_utf8(b.capture_id) && b.source_id.find('\0') == b.source_id.npos &&
                    b.capture_id.find('\0') == b.capture_id.npos && b.epoch && b.source_bytes &&
                    b.volume_bytes >= 512 && b.volume_offset <= b.source_bytes &&
                    b.volume_bytes <= b.source_bytes - b.volume_offset &&
                    s.record_source_offset >= b.volume_offset &&
                    s.record_source_offset - b.volume_offset <= b.volume_bytes - 32,
                "fat_content_stream_binding");
        require(p.read && p.applicable, "fat_content_stream_port");
        require(maximum && maximum <= 67108864, "fat_content_stream_bitmap_budget");
        const auto count = portable(b.source_bytes);
        require(!de_space_init(selected.binding.source_id.data(), selected.binding.source_id.size(),
                               &count, 1, &space),
                "fat_content_stream_binding");
    }
    void check() {
        bool valid = false;
        try {
            valid = port.applicable(selected.binding);
        } catch (...) {
        }
        if (!valid) {
            applicable = false;
            throw Stop{"fat_content_stream_source_changed"};
        }
    }
    Bytes read(std::uint64_t source, std::size_t count) {
        if (reads == budget.reads || count > budget.read_bytes - read_bytes)
            throw Yield{};
        const auto &b = selected.binding;
        if (!count || count > 4096 || source < b.volume_offset ||
            source - b.volume_offset > b.volume_bytes ||
            count > b.volume_bytes - (source - b.volume_offset))
            throw Stop{"fat_content_stream_range"};
        check();
        de_block_extent blocks{};
        de_byte_extent extent{};
        const auto start = portable(source), size = portable(count);
        if (de_extent_make(&space, &start, &size, &blocks) || de_extent_to_bytes(&blocks, &extent))
            throw Stop{"fat_content_stream_range"};
        ++reads;
        read_bytes += count;
        de_view view{};
        try {
            view = port.read(extent);
        } catch (...) {
            throw Stop{"fat_content_stream_reader_error"};
        }
        if (view.size > count || (view.size && !view.data))
            throw Stop{"fat_content_stream_reader_shape"};
        Bytes bytes;
        if (view.size)
            bytes.assign(view.data, view.data + view.size);
        receipts.items.push_back(V::object()
                                     .put("source_offset", number(source))
                                     .put("requested", number(count))
                                     .put("returned", number(bytes.size()))
                                     .put("sha256", V::string(hash(bytes))));
        check();
        if (bytes.size() != count)
            throw Stop{"fat_content_stream_short_read"};
        return bytes;
    }
    void verify_record() {
        const auto raw = read(selected.record_source_offset, 32);
        metadata.items.push_back(V::object()
                                     .put("kind", V::string("record"))
                                     .put("source_offset", number(selected.record_source_offset))
                                     .put("raw", V::string(hex(raw))));
        if (!std::equal(raw.begin(), raw.end(), selected.record.begin())) {
            applicable = false;
            throw Stop{"fat_content_stream_record_changed"};
        }
        record_verified = true;
    }
    void initialize() {
        if (stage == 0) {
            boot = read(selected.binding.volume_offset, 512);
            metadata.items.push_back(
                V::object().put("kind", V::string("boot_prefix")).put("raw", V::string(hex(boot))));
            de_view bytes{boot.data(), boot.size()};
            const auto available = portable(selected.binding.volume_bytes);
            if (de_fat_volume_read(&bytes, &available, &volume))
                throw Stop{"fat_content_stream_geometry"};
            stage = volume.bytes_per_sector > 512 && volume.bytes_per_sector <= 4096 ? 1 : 2;
        }
        if (stage == 1) {
            auto full = read(selected.binding.volume_offset, volume.bytes_per_sector);
            metadata.items.push_back(
                V::object().put("kind", V::string("boot_sector")).put("raw", V::string(hex(full))));
            if (!std::equal(boot.begin(), boot.end(), full.begin())) {
                applicable = false;
                throw Stop{"fat_content_stream_boot_changed"};
            }
            boot = std::move(full);
            de_view bytes{boot.data(), boot.size()};
            const auto available = portable(selected.binding.volume_bytes);
            if (de_fat_volume_read(&bytes, &available, &volume))
                throw Stop{"fat_content_stream_geometry"};
            stage = 2;
        }
        if (stage == 2) {
            if (!volume.usable_layout || selected.binding.fat_copy >= volume.fat_count)
                throw Stop{"fat_content_stream_geometry"};
            verify_record();
            de_view record{selected.record.data(), selected.record.size()};
            if (de_fat_dirent_read(&record, volume.bits, &file) ||
                file.kind != DE_FAT_DIRENT_FILE || file.dot ||
                (file.issues & (DE_FAT_DIR_TRUNCATED | DE_FAT_DIR_ATTRIBUTES | DE_FAT_DIR_CLUSTER |
                                DE_FAT_DIR_FILE_STATE)))
                throw Stop{"fat_content_stream_record"};
            const auto capacity =
                file.cluster ? (static_cast<std::uint64_t>(volume.cluster_count) + 7) / 8 : 0;
            if (capacity > bitmap_limit)
                throw Stop{"fat_content_stream_bitmap_budget"};
            bitmap.resize(static_cast<std::size_t>(capacity));
            if (de_fat_walk_init(volume.bits, volume.cluster_count, file.cluster,
                                 bitmap.empty() ? nullptr : bitmap.data(), bitmap.size(), &walk))
                throw Stop{"fat_content_stream_chain"};
            initialized = true;
            stage = 3;
        }
    }
    void advance() {
        if (cells.items.size() == budget.cells)
            throw Yield{};
        de_fat_cell_request request{};
        if (de_fat_walk_request(&walk, &request))
            throw Stop{"fat_content_stream_chain"};
        const auto table =
            static_cast<std::uint64_t>(volume.reserved_sectors) * volume.bytes_per_sector;
        const auto start = add(add(table, static_cast<std::uint64_t>(selected.binding.fat_copy) *
                                              native(volume.fat_bytes)),
                               native(request.offset));
        if (native(request.offset) > native(volume.fat_bytes) ||
            request.bytes > native(volume.fat_bytes) - native(request.offset))
            throw Stop{"fat_content_stream_table_range"};
        const auto source = add(selected.binding.volume_offset, start);
        auto raw = read(source, request.bytes);
        de_view bytes{raw.data(), raw.size()};
        de_fat_walk_step step{};
        if (de_fat_walk_feed(&walk, &bytes, &step))
            throw Stop{"fat_content_stream_chain"};
        cells.items.push_back(V::object()
                                  .put("ordinal", number(step.ordinal))
                                  .put("cluster", number(step.cluster))
                                  .put("source_offset", number(source))
                                  .put("raw", V::string(hex(raw)))
                                  .put("entry_kind", number(step.entry.kind))
                                  .put("value", number(step.entry.value))
                                  .put("chain", V::string(chain_name(walk.disposition))));
        if (!step.entry_present ||
            (step.entry.kind != DE_FAT_ENTRY_NEXT && step.entry.kind != DE_FAT_ENTRY_END))
            throw Stop{"fat_content_stream_chain_invalid"};
        const auto needed =
            (static_cast<std::uint64_t>(file.file_bytes) + volume.cluster_bytes - 1) /
            volume.cluster_bytes;
        excess = excess || walk.count > needed;
        cluster_at = add(selected.binding.volume_offset,
                         add(native(volume.data_offset_bytes),
                             static_cast<std::uint64_t>(step.cluster - 2) * volume.cluster_bytes));
        cluster_content = (std::min)(static_cast<std::uint64_t>(volume.cluster_bytes),
                                     static_cast<std::uint64_t>(file.file_bytes) - position);
        cluster_used = 0;
    }
    void run() {
        if (!initialized)
            initialize();
        if (!record_verified)
            verify_record();
        for (;;) {
            if (cluster_used < cluster_content) {
                if (data.size() == budget.bytes || reads == budget.reads ||
                    read_bytes == budget.read_bytes)
                    throw Yield{};
                const auto n = static_cast<std::size_t>(
                    (std::min)({std::uint64_t(4096), cluster_content - cluster_used,
                                static_cast<std::uint64_t>(budget.bytes - data.size()),
                                static_cast<std::uint64_t>(budget.read_bytes - read_bytes)}));
                auto bytes = read(add(cluster_at, cluster_used), n);
                chunks.items.push_back(
                    V::object()
                        .put("source_offset", number(add(cluster_at, cluster_used)))
                        .put("file_offset", number(position))
                        .put("bytes", number(n))
                        .put("sha256", V::string(hash(bytes))));
                data.insert(data.end(), bytes.begin(), bytes.end());
                position += n;
                cluster_used += n;
            } else if (walk.running)
                advance();
            else {
                stopped = true;
                if (walk.disposition != DE_FAT_CHAIN_END && walk.disposition != DE_FAT_CHAIN_EMPTY)
                    diagnostic = "fat_content_stream_chain_incomplete";
                else if (position != file.file_bytes)
                    diagnostic = "fat_content_stream_short_chain";
                return;
            }
        }
    }
    V next(const FatContentStreamSelection &s, const FatContentStreamBudget &b) {
        require(same(selected, s), "fat_content_stream_binding");
        validate(b);
        require(sequence != UINT64_MAX, "fat_content_stream_sequence");
        budget = b;
        reads = 0;
        read_bytes = 0;
        data.clear();
        cells = V::array();
        receipts = V::array();
        chunks = V::array();
        metadata = V::array();
        record_verified = false;
        const auto first = position;
        const bool was_active = !stopped;
        if (!stopped)
            try {
                check();
                run();
            } catch (const Yield &) {
            } catch (const Stop &s) {
                stopped = true;
                diagnostic = s.code;
            }
        if (was_active && (!stopped || diagnostic.empty()))
            try {
                check();
            } catch (const Stop &s) {
                stopped = true;
                diagnostic = s.code;
            }
        auto page = V::object()
                        .put("schema", V::string("org.disked.fat-content-stream-page/1"))
                        .put("selection", selection_value(selected))
                        .put("sequence", number(++sequence))
                        .put("previous_page_digest", previous.empty() ? V{} : V::string(previous))
                        .put("file_bytes", initialized ? number(file.file_bytes) : V{})
                        .put("file_offset", number(first))
                        .put("returned_bytes", number(data.size()))
                        .put("next_file_offset", number(position))
                        .put("data", V::string(hex(data)))
                        .put("data_sha256", V::string(hash(data)))
                        .put("chunks", std::move(chunks))
                        .put("cells", std::move(cells))
                        .put("reads", std::move(receipts))
                        .put("metadata", std::move(metadata))
                        .put("read_count", number(reads))
                        .put("read_bytes", number(read_bytes))
                        .put("allocation_count", initialized ? number(walk.count) : number(0))
                        .put("chain", V::string(initialized ? chain_name(walk.disposition)
                                                            : "not_established"))
                        .put("excess_allocation", V::boolean_value(excess))
                        .put("applicable", V::boolean_value(applicable))
                        .put("status", V::string(!stopped             ? "running"
                                                 : diagnostic.empty() ? "complete"
                                                                      : "partial"))
                        .put("diagnostic", diagnostic.empty() ? V{} : V::string(diagnostic))
                        .put("directory_membership", V::string("caller_not_authenticated"))
                        .put("atomic_snapshot", V::string("not_established"))
                        .put("authorizes_effects", V::boolean_value(false));
        previous = digest(page);
        page.put("page_digest", V::string(previous));
        require(json::dump(page, limits()).size() <= b.output_bytes,
                "fat_content_stream_output_budget");
        return page;
    }
};
FatContentStream::FatContentStream(const FatContentStreamSelection &s, const FatTraversalPort &p,
                                   std::size_t n)
    : impl_(new Impl(s, p, n)) {
}
FatContentStream::~FatContentStream() = default;
V FatContentStream::next(const FatContentStreamSelection &s, const FatContentStreamBudget &b) {
    return impl_->next(s, b);
}
bool FatContentStream::finished() const {
    return impl_->stopped;
}
} // namespace disked
