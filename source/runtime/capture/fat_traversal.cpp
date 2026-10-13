#include "fat_traversal.h"
#include "portable/fat/fat.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <deque>
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
void require(bool ok, const char *code) {
    if (!ok)
        throw FatTraversalError(code);
}
void checked(int status) {
    if (status)
        throw Stop{"fat_traversal_internal"};
}
std::uint64_t add(std::uint64_t a, std::uint64_t b) {
    if (b > std::numeric_limits<std::uint64_t>::max() - a)
        throw Stop{"fat_traversal_overflow"};
    return a + b;
}
de_u64 portable(std::uint64_t n) {
    de_u64 value{};
    const auto text = std::to_string(n);
    checked(de_u64_parse(text.data(), text.size(), &value));
    return value;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    checked(de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string hex(const Bytes &bytes) {
    const char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(bytes.size() * 2);
    for (auto b : bytes) {
        result += digits[b >> 4];
        result += digits[b & 15];
    }
    return result;
}
json::Limits json_limits() {
    json::Limits limits;
    limits.bytes = 4194304;
    limits.values = 262144;
    limits.string_bytes = 32768;
    limits.depth = 24;
    return limits;
}
std::string digest(const V &page) {
    const auto text =
        std::string("disked:fat-traversal-page:1\n") + json::dump(page, json_limits());
    unsigned char result[32];
    sha256(reinterpret_cast<const unsigned char *>(text.data()), text.size(), result);
    return "sha256:" + hex(Bytes(result, result + 32));
}
bool same(const FatTraversalBinding &a, const FatTraversalBinding &b) {
    return a.source_id == b.source_id && a.capture_id == b.capture_id && a.epoch == b.epoch &&
           a.source_bytes == b.source_bytes && a.volume_offset == b.volume_offset &&
           a.volume_bytes == b.volume_bytes && a.fat_copy == b.fat_copy;
}
V binding_value(const FatTraversalBinding &b) {
    return V::object()
        .put("source_id", V::string(b.source_id))
        .put("capture_id", V::string(b.capture_id))
        .put("capture_epoch", exact(b.epoch))
        .put("source_bytes", exact(b.source_bytes))
        .put("volume_offset", exact(b.volume_offset))
        .put("volume_bytes", exact(b.volume_bytes))
        .put("fat_copy", exact(b.fat_copy));
}
const char *chain_name(int disposition) {
    switch (disposition) {
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
void validate_budget(const FatTraversalPageBudget &b) {
    require(b.records && b.records <= 65536 && b.events && b.events <= 4096 && b.reads &&
                b.reads <= 65536 && b.read_bytes >= 4096 && b.read_bytes <= 4194304 &&
                b.output_bytes >= 32768 && b.output_bytes <= 1048576,
            "fat_traversal_page_budget");
}
struct Directory {
    std::string key = "root";
    std::size_t depth = 0;
    std::uint32_t first = 0;
};
} // namespace

struct FatTraversal::Impl {
    FatTraversalBinding binding;
    FatTraversalPort port;
    FatTraversalResources resources;
    de_block_space space{};
    de_fat_volume volume{};
    Bytes boot, walk_bitmap, directories_bitmap, sector, pending_slots;
    std::vector<std::uint64_t> pending_offsets;
    std::deque<Directory> queue;
    std::deque<V> pending_events;
    Directory directory;
    de_fat_walk walk{};
    FatTraversalPageBudget budget;
    std::size_t reads = 0, read_bytes = 0, records = 0;
    std::size_t sector_at = 0;
    std::uint64_t sequence = 0, total_records = 0, total_entries = 0, total_directories = 0;
    std::uint64_t region_offset = 0, region_bytes = 0, sector_offset = 0, ordinal = 0;
    bool initialized = false, full_boot_pending = false, active = false, fixed_root = false;
    bool region_pending = false, end_marker = false, records_complete = false, sector_short = false;
    bool stopped = false, applicable = true, coverage_complete = true;
    std::string diagnostic, previous_digest;

    Impl(const FatTraversalBinding &b, const FatTraversalPort &p, const FatTraversalResources &r)
        : binding(b), port(p), resources(r) {
        require(!b.source_id.empty() && b.source_id.size() <= 128 &&
                    b.source_id.find('\0') == std::string::npos && !b.capture_id.empty() &&
                    b.capture_id.size() <= 256 && json::valid_utf8(b.source_id) &&
                    json::valid_utf8(b.capture_id) && b.epoch && b.source_bytes &&
                    b.volume_bytes >= 512 && b.volume_offset <= b.source_bytes &&
                    b.volume_bytes <= b.source_bytes - b.volume_offset,
                "fat_traversal_binding");
        require(static_cast<bool>(p.read) && static_cast<bool>(p.applicable), "fat_traversal_port");
        require(r.bitmap_bytes && r.bitmap_bytes <= 67108864 && r.queued_directories &&
                    r.queued_directories <= 1048576 && r.depth && r.depth <= 65536,
                "fat_traversal_resources");
        const auto bytes = portable(b.source_bytes);
        checked(
            de_space_init(binding.source_id.data(), binding.source_id.size(), &bytes, 1, &space));
    }
    void check_applicable() {
        try {
            if (port.applicable(binding))
                return;
        } catch (...) {
        }
        applicable = false;
        throw Stop{"fat_traversal_capture_withdrawn"};
    }
    Bytes read(std::uint64_t offset, std::size_t amount) {
        if (reads == budget.reads || amount > budget.read_bytes - read_bytes)
            throw Yield{};
        if (offset > binding.volume_bytes || amount > binding.volume_bytes - offset)
            throw Stop{"fat_traversal_extent"};
        check_applicable();
        const auto start = portable(add(binding.volume_offset, offset));
        const auto length = portable(amount);
        de_block_extent blocks{};
        de_byte_extent extent{};
        checked(de_extent_make(&space, &start, &length, &blocks));
        checked(de_extent_to_bytes(&blocks, &extent));
        ++reads;
        read_bytes += amount;
        de_view view{};
        try {
            view = port.read(extent);
        } catch (...) {
            throw Stop{"fat_traversal_reader_error"};
        }
        check_applicable();
        if (view.size > amount || (!view.data && view.size))
            throw Stop{"fat_traversal_reader_shape"};
        return view.size ? Bytes(view.data, view.data + view.size) : Bytes{};
    }
    bool used(std::uint32_t cluster) const {
        const auto bit = cluster - 2;
        return (directories_bitmap[bit / 8] & (1u << (bit % 8))) != 0;
    }
    void mark(std::uint32_t cluster) {
        const auto bit = cluster - 2;
        directories_bitmap[bit / 8] |= static_cast<unsigned char>(1u << (bit % 8));
    }
    std::uint64_t cluster_offset(std::uint32_t cluster) const {
        if (cluster < 2 || cluster > volume.cluster_count + 1)
            throw Stop{"fat_traversal_cluster"};
        return add(native(volume.data_offset_bytes),
                   static_cast<std::uint64_t>(cluster - 2) * volume.cluster_bytes);
    }
    void emit(V event) {
        pending_events.push_back(std::move(event));
    }
    V event(const char *kind) const {
        return V::object().put("type", V::string(kind)).put("directory", V::string(directory.key));
    }
    void orphan(const char *reason) {
        if (pending_slots.empty())
            return;
        auto offsets = V::array();
        for (auto offset : pending_offsets)
            offsets.items.push_back(exact(offset));
        emit(event("orphan")
                 .put("reason", V::string(reason))
                 .put("raw_slots", V::string(hex(pending_slots)))
                 .put("source_offsets", std::move(offsets)));
        pending_slots.clear();
        pending_offsets.clear();
    }
    void finish_directory(const char *chain) {
        orphan("directory_end");
        if (!records_complete ||
            (std::string(chain) != "end" && std::string(chain) != "fixed_root"))
            coverage_complete = false;
        emit(event("directory_end")
                 .put("chain", V::string(chain))
                 .put("records_complete", V::boolean_value(records_complete))
                 .put("record_count", exact(ordinal)));
        active = false;
        region_pending = false;
        sector.clear();
        sector_at = 0;
    }
    void interrupt(const char *code) {
        if (!stopped) {
            orphan("interrupted");
            if (active)
                emit(event("directory_interrupted")
                         .put("reason", V::string(code))
                         .put("record_count", exact(ordinal)));
        }
        stopped = true;
        coverage_complete = false;
        if (diagnostic.empty())
            diagnostic = code;
    }
    void initialize() {
        if (boot.empty() && !full_boot_pending) {
            boot = read(0, 512);
            emit(V::object()
                     .put("type", V::string("boot_prefix"))
                     .put("raw", V::string(hex(boot)))
                     .put("source_offset", exact(binding.volume_offset))
                     .put("requested_bytes", exact(512)));
            if (boot.size() != 512)
                throw Stop{"fat_traversal_boot_short"};
            de_view bytes{boot.data(), boot.size()};
            const auto available = portable(binding.volume_bytes);
            checked(de_fat_volume_read(&bytes, &available, &volume));
            full_boot_pending = volume.bytes_per_sector > 512 && volume.bytes_per_sector <= 4096;
        }
        if (full_boot_pending) {
            auto whole = read(0, volume.bytes_per_sector);
            if (whole.size() != volume.bytes_per_sector) {
                emit(V::object()
                         .put("type", V::string("boot_prefix"))
                         .put("raw", V::string(hex(whole)))
                         .put("source_offset", exact(binding.volume_offset))
                         .put("requested_bytes", exact(volume.bytes_per_sector)));
                throw Stop{"fat_traversal_boot_short"};
            }
            if (!std::equal(boot.begin(), boot.end(), whole.begin())) {
                emit(V::object()
                         .put("type", V::string("boot_conflict"))
                         .put("original_prefix", V::string(hex(boot)))
                         .put("observed_sector", V::string(hex(whole))));
                applicable = false;
                throw Stop{"fat_traversal_boot_changed"};
            }
            boot = std::move(whole);
            de_view bytes{boot.data(), boot.size()};
            const auto available = portable(binding.volume_bytes);
            checked(de_fat_volume_read(&bytes, &available, &volume));
            full_boot_pending = false;
        }
        emit(V::object()
                 .put("type", V::string("volume"))
                 .put("boot_raw", V::string(hex(boot)))
                 .put("bits", exact(static_cast<std::uint64_t>(volume.bits)))
                 .put("issues", exact(volume.issues))
                 .put("usable_layout", V::boolean_value(volume.usable_layout != 0))
                 .put("cluster_count", exact(volume.cluster_count))
                 .put("cluster_bytes", exact(volume.cluster_bytes))
                 .put("active_copy_selected",
                      V::boolean_value(binding.fat_copy < volume.fat_count &&
                                       (volume.mirrored || volume.bits != 32 ||
                                        binding.fat_copy == (volume.flags & 15)))));
        if (!volume.usable_layout)
            throw Stop{"fat_traversal_layout_unusable"};
        if (binding.fat_copy >= volume.fat_count)
            throw Stop{"fat_traversal_copy_range"};
        const std::size_t bitmap = volume.cluster_count / 8 + (volume.cluster_count % 8 != 0);
        if (bitmap > resources.bitmap_bytes / 2)
            throw Stop{"fat_traversal_bitmap_budget"};
        walk_bitmap.resize(bitmap);
        directories_bitmap.resize(bitmap);
        Directory root;
        root.first = volume.root_cluster;
        queue.push_back(root);
        initialized = true;
    }
    void activate() {
        if (queue.empty()) {
            stopped = true;
            return;
        }
        directory = queue.front();
        queue.pop_front();
        ordinal = 0;
        end_marker = false;
        records_complete = false;
        sector.clear();
        sector_at = 0;
        sector_short = false;
        region_pending = false;
        active = true;
        ++total_directories;
        fixed_root = directory.key == "root" && volume.bits != 32;
        emit(event("directory_begin")
                 .put("first_cluster", exact(directory.first))
                 .put("depth", exact(directory.depth)));
        if (fixed_root) {
            region_offset =
                static_cast<std::uint64_t>(volume.reserved_sectors) * volume.bytes_per_sector +
                static_cast<std::uint64_t>(volume.fat_count) * native(volume.fat_bytes);
            region_bytes = static_cast<std::uint64_t>(volume.root_entries) * 32;
            region_pending = true;
        } else {
            checked(de_fat_walk_init(volume.bits, volume.cluster_count, directory.first,
                                     walk_bitmap.data(), walk_bitmap.size(), &walk));
            if (!walk.running)
                finish_directory(chain_name(walk.disposition));
        }
    }
    void allocation() {
        if (!walk.running) {
            finish_directory(chain_name(walk.disposition));
            return;
        }
        if (used(walk.current)) {
            finish_directory("storage_reused");
            return;
        }
        de_fat_cell_request request{};
        checked(de_fat_walk_request(&walk, &request));
        const auto offset =
            add(static_cast<std::uint64_t>(volume.reserved_sectors) * volume.bytes_per_sector +
                    static_cast<std::uint64_t>(binding.fat_copy) * native(volume.fat_bytes),
                native(request.offset));
        auto cell = read(offset, request.bytes);
        de_view bytes{cell.data(), cell.size()};
        de_fat_walk_step step{};
        checked(de_fat_walk_feed(&walk, &bytes, &step));
        mark(step.cluster);
        emit(event("allocation")
                 .put("cluster", exact(step.cluster))
                 .put("ordinal", exact(step.ordinal))
                 .put("source_offset", exact(add(binding.volume_offset, offset)))
                 .put("raw_cell", V::string(hex(cell)))
                 .put("entry_present", V::boolean_value(step.entry_present != 0))
                 .put("raw_value", exact(step.entry.raw_value))
                 .put("value", exact(step.entry.value))
                 .put("kind", exact(static_cast<std::uint64_t>(step.entry.kind))));
        if (!step.entry_present) {
            finish_directory("truncated");
            return;
        }
        if (end_marker)
            return;
        region_offset = cluster_offset(step.cluster);
        region_bytes = volume.cluster_bytes;
        region_pending = true;
    }
    void record(const Bytes &raw, std::uint64_t source_offset) {
        de_view bytes{raw.data(), raw.size()};
        de_fat_dirent entry{};
        checked(de_fat_dirent_read(&bytes, volume.bits, &entry));
        ++ordinal;
        total_records = add(total_records, 1);
        ++records;
        if (entry.kind == DE_FAT_DIRENT_LONG) {
            if ((entry.ordinal & 64) && !pending_slots.empty())
                orphan("replaced_start");
            if (pending_slots.size() == DE_FAT_LFN_MAX_SLOTS * 32)
                orphan("slot_budget");
            pending_slots.insert(pending_slots.end(), raw.begin(), raw.end());
            pending_offsets.push_back(source_offset);
            return;
        }
        if (entry.kind == DE_FAT_DIRENT_END) {
            orphan("end_marker");
            end_marker = true;
            records_complete = true;
            emit(event("end_marker")
                     .put("source_offset", exact(source_offset))
                     .put("raw", V::string(hex(raw))));
            sector.clear();
            sector_at = 0;
            region_pending = false;
            return;
        }
        if (entry.kind == DE_FAT_DIRENT_DELETED)
            orphan("deleted_boundary");
        const auto key = "entry:" + std::to_string(source_offset);
        auto value = event("record")
                         .put("key", V::string(key))
                         .put("source_offset", exact(source_offset))
                         .put("directory_ordinal", exact(ordinal - 1))
                         .put("depth", exact(directory.depth + 1))
                         .put("raw", V::string(hex(raw)))
                         .put("kind", exact(static_cast<std::uint64_t>(entry.kind)))
                         .put("issues", exact(entry.issues))
                         .put("attributes", exact(entry.attributes))
                         .put("case_flags", exact(entry.case_flags))
                         .put("raw_cluster", exact(entry.raw_cluster))
                         .put("cluster", exact(entry.cluster))
                         .put("file_bytes", exact(entry.file_bytes))
                         .put("dot", exact(entry.dot))
                         .put("creation_time", exact(entry.creation_time))
                         .put("creation_date", exact(entry.creation_date))
                         .put("creation_fraction", exact(entry.creation_fraction))
                         .put("access_date", exact(entry.access_date))
                         .put("write_time", exact(entry.write_time))
                         .put("write_date", exact(entry.write_date));
        if (!pending_slots.empty()) {
            de_view slots{pending_slots.data(), pending_slots.size()};
            de_fat_lfn name{};
            checked(de_fat_lfn_read(&slots, &bytes, volume.bits, &name));
            auto units = V::array(), offsets = V::array();
            for (std::size_t i = 0; i < name.unit_count; ++i)
                units.items.push_back(exact(name.units[i]));
            for (auto offset : pending_offsets)
                offsets.items.push_back(exact(offset));
            char display[1561];
            checked(de_fat_name_display(name.units, name.name_length, display, sizeof(display)));
            value.put("long_name",
                      V::object()
                          .put("raw_slots", V::string(hex(pending_slots)))
                          .put("source_offsets", std::move(offsets))
                          .put("units", std::move(units))
                          .put("name_length", exact(name.name_length))
                          .put("issues", exact(name.issues))
                          .put("associated", V::boolean_value(name.associated != 0))
                          .put("unicode_valid", V::boolean_value(name.unicode_valid != 0))
                          .put("canonical", V::boolean_value(name.canonical_name != 0))
                          .put("display", V::string(display)));
            pending_slots.clear();
            pending_offsets.clear();
        }
        emit(std::move(value));
        total_entries = add(total_entries, 1);
        if (entry.kind == DE_FAT_DIRENT_DIRECTORY && !entry.dot) {
            if (entry.issues &
                (DE_FAT_DIR_ATTRIBUTES | DE_FAT_DIR_CLUSTER | DE_FAT_DIR_FILE_STATE)) {
                coverage_complete = false;
                emit(event("directory_not_followed")
                         .put("key", V::string(key))
                         .put("reason", V::string("entry_metadata")));
                return;
            }
            if (directory.depth == resources.depth)
                throw Stop{"fat_traversal_depth_budget"};
            if (queue.size() == resources.queued_directories)
                throw Stop{"fat_traversal_queue_budget"};
            Directory child;
            child.key = key;
            child.first = entry.cluster;
            child.depth = directory.depth + 1;
            queue.push_back(std::move(child));
        }
    }
    void advance() {
        if (!initialized) {
            initialize();
            return;
        }
        if (!active) {
            activate();
            return;
        }
        if (sector_at < sector.size()) {
            if (sector.size() - sector_at < 32) {
                emit(event("record_tail")
                         .put("source_offset",
                              exact(add(binding.volume_offset, sector_offset + sector_at)))
                         .put("raw",
                              V::string(hex(Bytes(sector.begin() + sector_at, sector.end())))));
                orphan("short_region");
                throw Stop{"fat_traversal_directory_short"};
            }
            if (records == budget.records)
                throw Yield{};
            const auto offset = sector_at;
            sector_at += 32;
            record(Bytes(sector.begin() + offset, sector.begin() + offset + 32),
                   add(binding.volume_offset, sector_offset + offset));
            return;
        }
        if (sector_short) {
            orphan("short_region");
            throw Stop{"fat_traversal_directory_short"};
        }
        if (region_pending && region_bytes && !end_marker) {
            const auto amount = static_cast<std::size_t>(
                std::min<std::uint64_t>(volume.bytes_per_sector, region_bytes));
            auto bytes = read(region_offset, amount);
            sector_offset = region_offset;
            sector_at = 0;
            sector_short = bytes.size() != amount;
            sector = std::move(bytes);
            region_offset += amount;
            region_bytes -= amount;
            return;
        }
        region_pending = false;
        if (fixed_root) {
            records_complete = true;
            finish_directory("fixed_root");
            return;
        }
        if (!walk.running) {
            if (walk.disposition == DE_FAT_CHAIN_END)
                records_complete = true;
            finish_directory(chain_name(walk.disposition));
            return;
        }
        allocation();
    }
    V next(const FatTraversalBinding &expected, const FatTraversalPageBudget &b) {
        require(same(binding, expected), "fat_traversal_binding_mismatch");
        validate_budget(b);
        require(!(stopped && pending_events.empty()), "fat_traversal_finished");
        require(sequence != std::numeric_limits<std::uint64_t>::max(),
                "fat_traversal_sequence_exhausted");
        budget = b;
        reads = read_bytes = records = 0;
        auto events = V::array();
        std::size_t output_bytes = 8192;
        try {
            check_applicable();
            for (;;) {
                if (!pending_events.empty()) {
                    const auto size = json::dump(pending_events.front(), json_limits()).size() + 1;
                    if (events.items.size() == b.events || size > b.output_bytes - output_bytes)
                        break;
                    output_bytes += size;
                    events.items.push_back(std::move(pending_events.front()));
                    pending_events.pop_front();
                    continue;
                }
                if (stopped || events.items.size() == b.events)
                    break;
                advance();
            }
            check_applicable();
        } catch (const Yield &) {
            try {
                check_applicable();
            } catch (const Stop &s) {
                interrupt(s.code);
            }
        } catch (const Stop &s) {
            interrupt(s.code);
        }
        // Retain queued events after a terminal read/resource outcome and drain
        // them on subsequent pages. A withdrawn capture cannot resume I/O.
        while (!pending_events.empty() && events.items.size() < b.events) {
            const auto size = json::dump(pending_events.front(), json_limits()).size() + 1;
            if (size > b.output_bytes - output_bytes)
                break;
            output_bytes += size;
            events.items.push_back(std::move(pending_events.front()));
            pending_events.pop_front();
        }
        auto page = V::object()
                        .put("schema", V::string("org.disked.fat-traversal-page/1"))
                        .put("binding", binding_value(binding))
                        .put("sequence", exact(++sequence))
                        .put("previous_page_digest",
                             previous_digest.empty() ? V{} : V::string(previous_digest))
                        .put("events", std::move(events))
                        .put("applicable", V::boolean_value(applicable))
                        .put("status", V::string(stopped && pending_events.empty()
                                                     ? (coverage_complete ? "complete" : "partial")
                                                     : "running"))
                        .put("diagnostic", diagnostic.empty() ? V{} : V::string(diagnostic))
                        .put("totals", V::object()
                                           .put("records", exact(total_records))
                                           .put("entries", exact(total_entries))
                                           .put("directories", exact(total_directories)))
                        .put("page_work", V::object()
                                              .put("reads", exact(reads))
                                              .put("read_bytes", exact(read_bytes))
                                              .put("records", exact(records)))
                        .put("binding_verification", V::string("caller_port_only"))
                        .put("atomic_snapshot", V::string("not_established"))
                        .put("filesystem_health", V::string("not_established"));
        previous_digest = digest(page);
        page.put("page_digest", V::string(previous_digest));
        require(json::dump(page, json_limits()).size() <= b.output_bytes,
                "fat_traversal_output_budget");
        return page;
    }
};
FatTraversal::FatTraversal(const FatTraversalBinding &b, const FatTraversalPort &p,
                           const FatTraversalResources &r)
    : impl_(new Impl(b, p, r)) {
}
FatTraversal::~FatTraversal() = default;
FatTraversal::FatTraversal(FatTraversal &&) noexcept = default;
FatTraversal &FatTraversal::operator=(FatTraversal &&) noexcept = default;
V FatTraversal::next(const FatTraversalBinding &b, const FatTraversalPageBudget &budget) {
    require(static_cast<bool>(impl_), "fat_traversal_moved");
    return impl_->next(b, budget);
}
bool FatTraversal::finished() const {
    return !impl_ || (impl_->stopped && impl_->pending_events.empty());
}
} // namespace disked
