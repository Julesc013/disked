#include "fat_tree_snapshot.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <set>
#include <vector>

namespace disked {
namespace {
using V = json::Value;
void require(bool ok, const char *code = "fat_tree_shape") {
    if (!ok)
        throw std::invalid_argument(code);
}
const V &get(const V &v, const char *key) {
    const auto *p = v.find(key);
    require(p != nullptr);
    return *p;
}
std::string text(const V &v) {
    require(v.kind == V::Kind::string);
    return v.text;
}
std::string text(const V &v, const char *key) {
    return text(get(v, key));
}
std::uint64_t integer(const V &v) {
    const auto s = text(v);
    require(json::decimal_u64(s));
    return std::stoull(s);
}
std::uint64_t integer(const V &v, const char *key) {
    return integer(get(v, key));
}
std::size_t bounded(const V &v, const char *key, std::uint64_t maximum) {
    const auto n = integer(v, key);
    require(n <= maximum, "fat_tree_input_bound");
    return static_cast<std::size_t>(n);
}
bool boolean(const V &v, const char *key) {
    const auto &p = get(v, key);
    require(p.kind == V::Kind::boolean);
    return p.boolean;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    require(v.kind == V::Kind::object && v.fields.size() == keys.size());
    for (const auto &p : v.fields)
        require(keys.count(p.first) != 0);
}
bool equal(const V &a, const V &b) {
    return json::dump(a, fat_tree_json_limits()) == json::dump(b, fat_tree_json_limits());
}
std::string hash(const V &v) {
    const auto bytes = json::dump(v, fat_tree_json_limits());
    unsigned char result[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), result);
    const char digits[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (auto b : result) {
        out += digits[b >> 4];
        out += digits[b & 15];
    }
    return out;
}
void metadata(const V &v) {
    exact(v, {"volume_id", "file_id", "bytes", "created", "written", "changed", "attributes",
              "hardlinks"});
    integer(v, "volume_id");
    integer(v, "bytes");
    require(integer(v, "attributes") <= 0xffffffffULL && integer(v, "hardlinks") == 1,
            "fat_tree_source_metadata");
    const auto id = text(v, "file_id");
    require(id.size() == 32 && id.find_first_not_of("0123456789abcdef") == id.npos,
            "fat_tree_source_metadata");
    for (const auto key : {"created", "written", "changed"}) {
        const auto s = text(v, key);
        require(!s.empty() && s.size() <= 20 && std::to_string(std::stoll(s)) == s,
                "fat_tree_source_metadata");
    }
}
std::vector<unsigned char> unhex(const V &v, std::size_t maximum) {
    const auto s = text(v);
    require(s.size() % 2 == 0 && s.size() / 2 <= maximum &&
                s.find_first_not_of("0123456789abcdef") == s.npos,
            "fat_tree_region_bytes");
    auto digit = [](char c) { return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10); };
    std::vector<unsigned char> bytes(s.size() / 2);
    for (std::size_t i = 0; i < bytes.size(); ++i)
        bytes[i] = static_cast<unsigned char>(digit(s[i * 2]) * 16 + digit(s[i * 2 + 1]));
    return bytes;
}
void fixture(const V &v) {
    require(v.kind == V::Kind::object, "fat_tree_fixture");
#ifndef DISKED_FAT_TREE_SNAPSHOT_TESTING
    require(v.fields.empty(), "fat_tree_fixture_not_compiled");
#else
    const std::map<std::string, std::set<std::string>> modes = {
        {"file_fault", {"read_error", "short_read", "verify_changed", "metadata_changed", "hold"}},
        {"worker_fault",
         {"hang", "late", "frame_changed", "region_changed", "checks_changed", "process_changed",
          "page_digest", "page_context", "hold"}},
        {"startup_fault", {"before_spawn", "after_spawn", "after_spawn_alloc"}},
        {"reply_fault",
         {"capture", "worker", "code", "request", "scope", "host", "observer", "attempt", "pid",
          "created", "shape", "status", "claims", "schema", "digest", "hold"}}};
    for (const auto &p : v.fields) {
        const auto it = modes.find(p.first);
        require(it != modes.end() && it->second.count(text(p.second)), "fat_tree_fixture");
    }
#endif
}
} // namespace
json::Limits fat_tree_json_limits() {
    json::Limits l;
    l.bytes = fat_tree_frame_bytes;
    l.values = 65536;
    l.depth = 32;
    l.string_bytes = 32768;
    return l;
}
void validate_fat_tree_input(const FatTreeInput &v) {
    metadata(v.expected_source);
    fixture(v.fixture);
    require(!v.path.empty() && v.path.size() <= 960 && json::valid_utf8(v.path) &&
                v.path.find('\0') == v.path.npos,
            "fat_tree_path");
    const auto bytes = integer(v.expected_source, "bytes");
    require(v.capture_epoch && bytes <= 0x7fffffffffffffffULL && v.volume_bytes >= 512 &&
                v.volume_offset <= bytes && v.volume_bytes <= bytes - v.volume_offset,
            "fat_tree_window");
    const auto &r = v.resources;
    require(r.bitmap_bytes && r.bitmap_bytes <= 67108864 && r.queued_directories &&
                r.queued_directories <= 65536 && r.depth && r.depth <= 1024,
            "fat_tree_resources");
    const auto &b = v.page;
    require(b.records && b.records <= 1024 && b.events && b.events <= 512 && b.reads &&
                b.reads <= 512 && b.read_bytes >= 4096 && b.read_bytes <= 65536 &&
                b.output_bytes >= 32768 && b.output_bytes <= 65536,
            "fat_tree_page_budget");
}
V fat_tree_input_value(const FatTreeInput &v) {
    validate_fat_tree_input(v);
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-input/1"))
        .put("path", V::string(v.path))
        .put("expected_source", v.expected_source)
        .put("capture_epoch", number(v.capture_epoch))
        .put("volume_offset", number(v.volume_offset))
        .put("volume_bytes", number(v.volume_bytes))
        .put("fat_copy", number(v.fat_copy))
        .put("resources", V::object()
                              .put("bitmap_bytes", number(v.resources.bitmap_bytes))
                              .put("queued_directories", number(v.resources.queued_directories))
                              .put("depth", number(v.resources.depth)))
        .put("page", V::object()
                         .put("records", number(v.page.records))
                         .put("events", number(v.page.events))
                         .put("reads", number(v.page.reads))
                         .put("read_bytes", number(v.page.read_bytes))
                         .put("output_bytes", number(v.page.output_bytes)))
        .put("fixture", v.fixture);
}
FatTreeInput fat_tree_input_from(const V &header) {
    auto v = header.find("provider_input") ? get(header, "provider_input") : header;
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *p = v.find(key)) {
            const auto *declared = get(v, "fixture").find(key);
            require(declared && equal(*declared, *p), "fat_tree_fixture");
            v.fields.erase(key);
        }
    exact(v, {"schema", "path", "expected_source", "capture_epoch", "volume_offset", "volume_bytes",
              "fat_copy", "resources", "page", "fixture"});
    require(text(v, "schema") == "org.disked.fat-tree-input/1", "fat_tree_input_schema");
    FatTreeInput out;
    out.path = text(v, "path");
    out.expected_source = get(v, "expected_source");
    out.capture_epoch = integer(v, "capture_epoch");
    out.volume_offset = integer(v, "volume_offset");
    out.volume_bytes = integer(v, "volume_bytes");
    require(integer(v, "fat_copy") <= 0xffffffffULL);
    out.fat_copy = static_cast<std::uint32_t>(integer(v, "fat_copy"));
    const auto &r = get(v, "resources"), &b = get(v, "page");
    exact(r, {"bitmap_bytes", "queued_directories", "depth"});
    exact(b, {"records", "events", "reads", "read_bytes", "output_bytes"});
    out.resources = {bounded(r, "bitmap_bytes", 67108864), bounded(r, "queued_directories", 65536),
                     bounded(r, "depth", 1024)};
    out.page = {bounded(b, "records", 1024), bounded(b, "events", 512), bounded(b, "reads", 512),
                bounded(b, "read_bytes", 65536), bounded(b, "output_bytes", 65536)};
    out.fixture = get(v, "fixture");
    validate_fat_tree_input(out);
    return out;
}
FatTraversalBinding fat_tree_binding(const FatTreeInput &input, const V &context) {
    exact(context, {"process_id", "process_created", "capture_sequence"});
    require(integer(context, "process_id") && integer(context, "process_id") <= 0xffffffffULL &&
                integer(context, "process_created") && integer(context, "capture_sequence"),
            "fat_tree_process_context");
    FatTraversalBinding b;
    b.source_id = hash(input.expected_source);
    b.capture_id = hash(V::object()
                            .put("process", context)
                            .put("source", input.expected_source)
                            .put("capture_epoch", number(input.capture_epoch)));
    b.epoch = input.capture_epoch;
    b.source_bytes = integer(input.expected_source, "bytes");
    b.volume_offset = input.volume_offset;
    b.volume_bytes = input.volume_bytes;
    b.fat_copy = input.fat_copy;
    return b;
}
V fat_tree_binding_value(const FatTraversalBinding &b) {
    return V::object()
        .put("source_id", V::string(b.source_id))
        .put("capture_id", V::string(b.capture_id))
        .put("capture_epoch", number(b.epoch))
        .put("source_bytes", number(b.source_bytes))
        .put("volume_offset", number(b.volume_offset))
        .put("volume_bytes", number(b.volume_bytes))
        .put("fat_copy", number(b.fat_copy));
}
V fat_tree_claims() {
    return V::object()
        .put("atomic_snapshot", V::boolean_value(false))
        .put("current_source_authority", V::boolean_value(false))
        .put("filesystem_health", V::boolean_value(false))
        .put("physical_admission", V::boolean_value(false))
        .put("mutation_authority", V::boolean_value(false));
}
struct FatTreeReplay::Impl {
    FatTreeInput input;
    V context;
    FatTraversalBinding binding;
    std::unique_ptr<FatTraversal> traversal;
    const V *current = nullptr;
    std::size_t read_at = 0, check_at = 0;
    std::vector<unsigned char> bytes;
    bool read_consistent = true, protocol_error = false, failed = false;
    explicit Impl(const FatTreeInput &v) : input(v) {
        validate_fat_tree_input(input);
    }
    bool check() {
        try {
            const auto &items = get(*current, "checks").items;
            require(check_at < items.size());
            const auto &item = items[check_at++];
            exact(item, {"applicable", "cancelled", "read_consistent", "metadata", "code",
                         "platform_code"});
            require(boolean(item, "read_consistent") == read_consistent, "fat_tree_check_receipt");
            require(integer(item, "platform_code") <= 0xffffffffULL, "fat_tree_check_receipt");
            const auto &observed = get(item, "metadata"), &code = get(item, "code");
            if (observed.kind != V::Kind::null)
                metadata(observed);
            if (code.kind != V::Kind::null) {
                const auto s = text(code);
                require(!s.empty() && s.size() <= 128 && s.find('\0') == s.npos &&
                            json::valid_utf8(s),
                        "fat_tree_check_code");
            }
            const bool applies = !boolean(item, "cancelled") && read_consistent &&
                                 code.kind == V::Kind::null &&
                                 equal(observed, input.expected_source);
            require(boolean(item, "applicable") == applies, "fat_tree_check_receipt");
            return applies;
        } catch (const std::exception &) {
            protocol_error = true;
            return false;
        }
    }
    de_view read(const de_byte_extent &extent) {
        try {
            const auto &items = get(*current, "regions").items;
            require(read_at < items.size());
            const auto &item = items[read_at++];
            exact(item, {"offset", "requested", "bytes", "read_error", "reread_bytes",
                         "reread_error", "matches"});
            char start[21], end[21];
            require(!de_u64_format(&extent.start, start, sizeof(start)) &&
                    !de_u64_format(&extent.end, end, sizeof(end)));
            const auto at = std::stoull(start), last = std::stoull(end);
            require(last >= at && last - at <= 4096 && at == integer(item, "offset") &&
                        last - at == integer(item, "requested"),
                    "fat_tree_region_coordinate");
            bytes = unhex(get(item, "bytes"), static_cast<std::size_t>(last - at));
            const auto reread =
                unhex(get(item, "reread_bytes"), static_cast<std::size_t>(last - at));
            const auto first_error = integer(item, "read_error"),
                       second_error = integer(item, "reread_error");
            require(first_error <= 0xffffffffULL && second_error <= 0xffffffffULL);
            require((!first_error || bytes.empty()) && (!second_error || reread.empty()),
                    "fat_tree_region_error");
            const bool matches = !first_error && !second_error && bytes.size() == last - at &&
                                 reread.size() == last - at && bytes == reread;
            require(boolean(item, "matches") == matches, "fat_tree_region_receipt");
            read_consistent = read_consistent && matches;
            return de_view{bytes.data(), bytes.size()};
        } catch (const std::exception &) {
            protocol_error = true;
            return de_view{nullptr, 0};
        }
    }
    V accept(const V &frame) {
        require(!failed, "fat_tree_replay_failed");
        try {
            exact(frame, {"schema", "input", "context", "source_before", "source_after", "page",
                          "regions", "checks"});
            require(text(frame, "schema") == "org.disked.fat-tree-frame/1",
                    "fat_tree_frame_schema");
            require(equal(get(frame, "input"), fat_tree_input_value(input)) &&
                        equal(get(frame, "source_before"), input.expected_source),
                    "fat_tree_frame_input");
            const auto &regions = get(frame, "regions"), &checks = get(frame, "checks");
            require(regions.kind == V::Kind::array && regions.items.size() <= input.page.reads &&
                        checks.kind == V::Kind::array && !checks.items.empty() &&
                        checks.items.size() <= 2 * input.page.reads + 2,
                    "fat_tree_frame_budget");
            current = &frame;
            read_at = check_at = 0;
            protocol_error = false;
            if (!traversal) {
                context = get(frame, "context");
                binding = fat_tree_binding(input, context);
                FatTraversalPort port;
                port.read = [this](const de_byte_extent &e) { return read(e); };
                port.applicable = [this](const FatTraversalBinding &) { return check(); };
                traversal.reset(new FatTraversal(binding, port, input.resources));
            }
            require(equal(context, get(frame, "context")), "fat_tree_frame_context");
            auto expected = traversal->next(binding, input.page);
            require(!protocol_error && read_at == regions.items.size() &&
                        check_at == checks.items.size(),
                    "fat_tree_replay_callbacks");
            require(equal(expected, get(frame, "page")), "fat_tree_replay_page");
            require(equal(get(frame, "source_after"), get(checks.items.back(), "metadata")),
                    "fat_tree_source_after");
            current = nullptr;
            return expected;
        } catch (...) {
            current = nullptr;
            failed = true;
            throw;
        }
    }
};
FatTreeReplay::FatTreeReplay(const FatTreeInput &v) : impl_(new Impl(v)) {
}
FatTreeReplay::~FatTreeReplay() = default;
V FatTreeReplay::accept(const V &v) {
    return impl_->accept(v);
}
bool FatTreeReplay::finished() const {
    return impl_->failed || (impl_->traversal && impl_->traversal->finished());
}
} // namespace disked
