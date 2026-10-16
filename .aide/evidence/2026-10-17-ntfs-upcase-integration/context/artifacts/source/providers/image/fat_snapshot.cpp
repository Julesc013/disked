#include "fat_snapshot.h"
#include "local_file.h"
#include "platform/windows/file_names.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("fat_snapshot_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("fat_snapshot_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw std::invalid_argument("fat_snapshot_integer");
    return std::stoull(s);
}
bool boolean(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::boolean)
        throw std::invalid_argument("fat_snapshot_shape");
    return p.boolean;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        throw std::invalid_argument("fat_snapshot_shape");
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            throw std::invalid_argument("fat_snapshot_shape");
}
bool same(const V &a, const V &b) {
    return json::dump(a, fat_snapshot_json_limits()) == json::dump(b, fat_snapshot_json_limits());
}
std::string hex(const unsigned char *bytes, std::size_t count) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(count * 2);
    for (std::size_t i = 0; i < count; ++i) {
        out += digits[bytes[i] >> 4];
        out += digits[bytes[i] & 15];
    }
    return out;
}
std::string hash(const unsigned char *bytes, std::size_t count) {
    unsigned char out[32];
    sha256(bytes, count, out);
    return "sha256:" + hex(out, 32);
}
std::string hash(const V &value) {
    const auto bytes = json::dump(value, fat_snapshot_json_limits());
    return hash(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size());
}
bool digest(const std::string &s) {
    return s.size() == 71 && s.substr(0, 7) == "sha256:" &&
           s.find_first_not_of("0123456789abcdef", 7) == s.npos;
}
std::vector<unsigned char> unhex(const std::string &s, std::size_t maximum) {
    if (s.size() % 2 || s.size() / 2 > maximum || s.find_first_not_of("0123456789abcdef") != s.npos)
        throw std::invalid_argument("fat_snapshot_bytes");
    auto digit = [](char c) { return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10); };
    std::vector<unsigned char> out(s.size() / 2);
    for (std::size_t i = 0; i < out.size(); ++i)
        out[i] = static_cast<unsigned char>(digit(s[i * 2]) * 16 + digit(s[i * 2 + 1]));
    return out;
}
void metadata(const V &v) {
    exact(v, {"volume_id", "file_id", "bytes", "created", "written", "changed", "attributes",
              "hardlinks"});
    integer(v, "volume_id");
    integer(v, "bytes");
    if (integer(v, "attributes") > 0xffffffffULL || integer(v, "hardlinks") != 1)
        throw std::invalid_argument("fat_snapshot_metadata");
    const auto id = text(v, "file_id");
    if (id.size() != 32 || id.find_first_not_of("0123456789abcdef") != id.npos)
        throw std::invalid_argument("fat_snapshot_metadata");
    for (const auto key : {"created", "written", "changed"}) {
        const auto s = text(v, key);
        if (s.size() > 20 || std::to_string(std::stoll(s)) != s)
            throw std::invalid_argument("fat_snapshot_metadata");
    }
}
FatCaptureRequest capture_request(const FatSnapshotInput &input, const FatNameConsumer *consumer,
                                  std::uint64_t sequence = 1) {
    FatCaptureRequest r;
    r.source_id = hash(input.expected_source);
    r.epoch = sequence;
    r.source_bytes = integer(input.expected_source, "bytes");
    r.volume_offset = input.volume_offset;
    r.volume_bytes = input.volume_bytes;
    r.fat_copy = input.fat_copy;
    r.limits = input.limits;
    r.allocation_scan = input.allocation_scan;
    r.allocation_window = input.allocation_window;
    r.auxiliary_checks = input.auxiliary_checks;
    r.namespace_consumer = consumer;
    r.namespace_queries = input.queries;
    r.namespace_limits = input.namespace_limits;
    return r;
}
V limit_value(const FatCaptureLimits &l) {
    auto v = V::object();
#define SAVE_LIMIT(name) v.put(#name, number(l.name))
    SAVE_LIMIT(nodes);
    SAVE_LIMIT(depth);
    SAVE_LIMIT(chain_clusters);
    SAVE_LIMIT(total_clusters);
    SAVE_LIMIT(records);
    SAVE_LIMIT(read_requests);
    SAVE_LIMIT(read_bytes);
    SAVE_LIMIT(orphan_groups);
    SAVE_LIMIT(output_bytes);
    SAVE_LIMIT(compare_copies);
    SAVE_LIMIT(allocation_clusters);
    SAVE_LIMIT(allocation_findings);
#undef SAVE_LIMIT
    return v;
}
std::uint64_t native(const de_u64 &n) {
    char s[21];
    if (de_u64_format(&n, s, sizeof(s)))
        throw std::invalid_argument("fat_snapshot_extent");
    return std::stoull(s);
}
} // namespace
json::Limits fat_snapshot_json_limits(bool content_enabled) {
    json::Limits l;
    l.bytes = fat_snapshot_payload_bytes;
    l.values = 524288;
    l.depth = 40;
    l.string_bytes = content_enabled ? 393216 : 32768;
    return l;
}
V fat_snapshot_claims() {
    return V::object()
        .put("physical_admission", V::boolean_value(false))
        .put("mutation_authority", V::boolean_value(false))
        .put("atomic_snapshot", V::boolean_value(false))
        .put("storage_consumer_qualified", V::boolean_value(false))
        .put("product_dispatch_admitted", V::boolean_value(false));
}
void validate_fat_snapshot_input(const FatSnapshotInput &input) {
    if (!input.capture_epoch || input.path.empty() || input.path.size() > 32768 ||
        !json::valid_utf8(input.path))
        throw std::invalid_argument("fat_snapshot_input");
    local_file::path_for(input.path);
    metadata(input.expected_source);
    if (input.content_enabled)
        validate_fat_file_content_request(input.content);
    if (!input.namespace_limits.comparisons || input.namespace_limits.comparisons > 65536 ||
        !input.namespace_limits.findings || input.namespace_limits.findings > 128 ||
        input.namespace_limits.output_bytes < 16384 || input.namespace_limits.output_bytes > 524288)
        throw std::invalid_argument("fat_snapshot_namespace_limits");
    FatNameConsumer consumer;
    if (input.name_code_page)
        consumer = windows_fat_name_consumer(input.name_code_page);
    validate_fat_capture_request(
        capture_request(input, input.name_code_page ? &consumer : nullptr));
    if (input.fixture.kind != V::Kind::object)
        throw std::invalid_argument("fat_snapshot_fixture");
    for (const auto &p : input.fixture.fields) {
#ifdef DISKED_FAT_WORKER_TESTING
        const std::set<std::string> captures = {"verify_changed",
                                                "verify_error",
                                                "metadata_changed",
                                                "read_error",
                                                "short_read",
                                                "overlap_changed",
                                                "content_error",
                                                "content_short",
                                                "content_verify_changed",
                                                "content_metadata_changed",
                                                "content_source_changed",
                                                "content_hold"};
        const std::set<std::string> workers = {"hang",
                                               "content_changed",
                                               "content_region_changed",
                                               "content_receipt_changed",
                                               "late",
                                               "payload_changed",
                                               "result_changed",
                                               "receipt_changed",
                                               "process_changed",
                                               "domain_changed",
                                               "row_changed",
                                               "claims"};
        const std::set<std::string> startups = {"before_spawn", "after_spawn", "after_spawn_alloc"};
        const std::set<std::string> replies = {
            "capture", "worker",  "code",  "request", "scope",  "host",   "observer", "attempt",
            "pid",     "created", "shape", "status",  "claims", "schema", "digest",   "hold"};
        if (p.second.kind != V::Kind::string ||
            (p.first != "capture_fault" && p.first != "worker_fault" &&
             p.first != "startup_fault" && p.first != "reply_fault"))
            throw std::invalid_argument("fat_snapshot_fixture");
        const auto &choices = p.first == "capture_fault"   ? captures
                              : p.first == "worker_fault"  ? workers
                              : p.first == "startup_fault" ? startups
                                                           : replies;
        if (!choices.count(p.second.text))
            throw std::invalid_argument("fat_snapshot_fixture");
#else
        (void)p;
        throw std::invalid_argument("fat_snapshot_fixture");
#endif
    }
}
V fat_snapshot_input_value(const FatSnapshotInput &input) {
    validate_fat_snapshot_input(input);
    auto queries = V::array();
    for (const auto &q : input.queries) {
        auto units = V::array();
        for (auto u : q.component)
            units.items.push_back(number(u));
        queries.items.push_back(
            V::object().put("directory", number(q.directory)).put("units", std::move(units)));
    }
    auto value = V::object()
                     .put("path", V::string(input.path))
                     .put("expected_source", input.expected_source)
                     .put("volume_offset", number(input.volume_offset))
                     .put("volume_bytes", number(input.volume_bytes))
                     .put("fat_copy", number(input.fat_copy))
                     .put("name_code_page", number(input.name_code_page))
                     .put("allocation_scan", V::boolean_value(input.allocation_scan))
                     .put("auxiliary_checks", V::boolean_value(input.auxiliary_checks))
                     .put("limits", limit_value(input.limits))
                     .put("queries", std::move(queries))
                     .put("namespace_limits",
                          V::object()
                              .put("comparisons", number(input.namespace_limits.comparisons))
                              .put("findings", number(input.namespace_limits.findings))
                              .put("output_bytes", number(input.namespace_limits.output_bytes)))
                     .put("fixture", input.fixture);
    if (input.allocation_window.clusters)
        value.put("allocation_window",
                  V::object()
                      .put("first_cluster", number(input.allocation_window.first_cluster))
                      .put("clusters", number(input.allocation_window.clusters)));
    if (input.content_enabled)
        value.put("content", fat_file_content_request_value(input.content));
    return value;
}
FatSnapshotInput fat_snapshot_input_from(const V &header) {
    FatSnapshotInput input;
    input.capture_epoch = integer(header, "capture_epoch");
    exact(field(header, "policy"), {});
    const auto &v = field(header, "provider_input");
    auto keys =
        std::set<std::string>{"path",     "expected_source", "volume_offset",    "volume_bytes",
                              "fat_copy", "name_code_page",  "allocation_scan",  "auxiliary_checks",
                              "limits",   "queries",         "namespace_limits", "fixture"};
    for (const auto key : {"startup_fault", "reply_fault", "allocation_window", "content"})
        if (v.find(key))
            keys.insert(key);
    exact(v, keys);
    input.path = text(v, "path");
    input.expected_source = field(v, "expected_source");
    if (const auto *content = v.find("content")) {
        input.content_enabled = true;
        input.content = fat_file_content_request_from(*content);
    }
    input.volume_offset = integer(v, "volume_offset");
    input.volume_bytes = integer(v, "volume_bytes");
    const auto copy = integer(v, "fat_copy"), page = integer(v, "name_code_page");
    if (copy > 0xffffffffULL || page > 0xffffffffULL)
        throw std::invalid_argument("fat_snapshot_integer");
    input.fat_copy = static_cast<std::uint32_t>(copy);
    input.name_code_page = static_cast<std::uint32_t>(page);
    input.allocation_scan = boolean(v, "allocation_scan");
    if (const auto *window = v.find("allocation_window")) {
        exact(*window, {"first_cluster", "clusters"});
        const auto first = integer(*window, "first_cluster"), count = integer(*window, "clusters");
        if (first < 2 || first > 268435446 || !count || count > 8192)
            throw std::invalid_argument("fat_allocation_window_input");
        input.allocation_window = {static_cast<std::uint32_t>(first),
                                   static_cast<std::uint32_t>(count)};
    }
    input.auxiliary_checks = boolean(v, "auxiliary_checks");
    input.fixture = field(v, "fixture");
    const auto &limits = field(v, "limits");
    exact(limits, {"nodes", "depth", "chain_clusters", "total_clusters", "records", "read_requests",
                   "read_bytes", "orphan_groups", "output_bytes", "compare_copies",
                   "allocation_clusters", "allocation_findings"});
#define LOAD_LIMIT(name)                                                                           \
    {                                                                                              \
        const auto n = integer(limits, #name);                                                     \
        if (n > 1048576ULL * 8)                                                                    \
            throw std::invalid_argument("fat_snapshot_limit");                                     \
        input.limits.name = static_cast<std::size_t>(n);                                           \
    }
    LOAD_LIMIT(nodes);
    LOAD_LIMIT(depth);
    LOAD_LIMIT(chain_clusters);
    LOAD_LIMIT(total_clusters);
    LOAD_LIMIT(records);
    LOAD_LIMIT(read_requests);
    LOAD_LIMIT(read_bytes);
    LOAD_LIMIT(orphan_groups);
    LOAD_LIMIT(output_bytes);
    LOAD_LIMIT(compare_copies);
    LOAD_LIMIT(allocation_clusters);
    LOAD_LIMIT(allocation_findings);
#undef LOAD_LIMIT
    const auto &names = field(v, "namespace_limits");
    exact(names, {"comparisons", "findings", "output_bytes"});
    for (const auto key : {"comparisons", "findings", "output_bytes"})
        if (integer(names, key) > 1048576)
            throw std::invalid_argument("fat_snapshot_limit");
    input.namespace_limits = {static_cast<std::size_t>(integer(names, "comparisons")),
                              static_cast<std::size_t>(integer(names, "findings")),
                              static_cast<std::size_t>(integer(names, "output_bytes"))};
    const auto &queries = field(v, "queries");
    if (queries.kind != V::Kind::array || queries.items.size() > 16)
        throw std::invalid_argument("fat_snapshot_queries");
    for (const auto &q : queries.items) {
        exact(q, {"directory", "units"});
        const auto id = integer(q, "directory");
        if (id >= 128)
            throw std::invalid_argument("fat_snapshot_query");
        const auto &units = field(q, "units");
        if (units.kind != V::Kind::array || units.items.size() > 255)
            throw std::invalid_argument("fat_snapshot_query");
        FatNameQuery query;
        query.directory = static_cast<std::size_t>(id);
        for (const auto &u : units.items) {
            if (u.kind != V::Kind::string || !json::decimal_u64(u.text) ||
                std::stoull(u.text) > 65535)
                throw std::invalid_argument("fat_snapshot_units");
            query.component.push_back(static_cast<std::uint16_t>(std::stoull(u.text)));
        }
        input.queries.push_back(std::move(query));
    }
    for (const auto key : {"startup_fault", "reply_fault"}) {
        const auto *nested = input.fixture.find(key);
        const auto *outer = v.find(key);
        if (bool(nested) != bool(outer) || (nested && !same(*nested, *outer)))
            throw std::invalid_argument("fat_snapshot_fixture");
    }
    validate_fat_snapshot_input(input);
    return input;
}
V read_fat_snapshot_frame(const FatSnapshotInput &input, const std::function<bool()> &stop) {
    validate_fat_snapshot_input(input);
    FatNameConsumer consumer;
    if (input.name_code_page)
        consumer = windows_fat_name_consumer(input.name_code_page);
    auto captured = capture_fat_file_owned(
        input.path, input.volume_offset, input.volume_bytes, input.fat_copy, input.limits,
        input.allocation_scan, input.auxiliary_checks, input.name_code_page ? &consumer : nullptr,
        input.queries, input.namespace_limits, &input.expected_source, stop,
        input.allocation_window, input.content_enabled ? &input.content : nullptr);
    auto regions = V::array();
    for (const auto &r : captured.regions)
        regions.items.push_back(V::object()
                                    .put("offset", number(r.offset))
                                    .put("requested", number(r.requested))
                                    .put("error", number(r.error))
                                    .put("bytes", V::string(hex(r.bytes.data(), r.bytes.size()))));
    auto frame = V::object()
                     .put("schema", V::string("org.disked.fat-region-frame/1"))
                     .put("capture_epoch", number(input.capture_epoch))
                     .put("process_id", number(captured.process_id))
                     .put("process_created", number(captured.process_created))
                     .put("result", std::move(captured.result))
                     .put("regions", std::move(regions));
    if (input.content_enabled) {
        auto payload = V::array();
        for (const auto &r : captured.content_regions)
            payload.items.push_back(
                V::object()
                    .put("offset", number(r.offset))
                    .put("requested", number(r.requested))
                    .put("error", number(r.error))
                    .put("bytes", V::string(hex(r.bytes.data(), r.bytes.size()))));
        frame.put("content_regions", std::move(payload));
    }
    json::dump(frame, fat_snapshot_json_limits(input.content_enabled));
    return frame;
}
V verify_fat_snapshot_frame(const V &frame, const FatSnapshotInput &input) {
    validate_fat_snapshot_input(input);
    auto frame_keys = std::set<std::string>{"schema",          "capture_epoch", "process_id",
                                            "process_created", "result",        "regions"};
    if (input.content_enabled)
        frame_keys.insert("content_regions");
    exact(frame, frame_keys);
    json::dump(frame, fat_snapshot_json_limits(input.content_enabled));
    if (text(frame, "schema") != "org.disked.fat-region-frame/1" ||
        integer(frame, "capture_epoch") != input.capture_epoch || !integer(frame, "process_id") ||
        integer(frame, "process_id") > 0xffffffffULL || !integer(frame, "process_created"))
        throw std::invalid_argument("fat_snapshot_binding");
    const auto &result = field(frame, "result");
    auto result_keys = std::set<std::string>{"schema", "observation", "capture",
                                             "authorizes_effects", "product_dispatch_admitted"};
    if (input.content_enabled)
        result_keys.insert("content");
    exact(result, result_keys);
    if (text(result, "schema") != "org.disked.fat-file-capture/1" ||
        boolean(result, "authorizes_effects") || boolean(result, "product_dispatch_admitted"))
        throw std::invalid_argument("fat_snapshot_claims");
    const auto &receipt = field(result, "capture");
    exact(receipt, {"source_before", "source_after", "metadata_equal", "source_identity_digest",
                    "capture_domain", "path", "resolved_path", "regions", "reread_bytes",
                    "overlaps_equal", "regions_equal", "observed_stable", "source_consistency",
                    "atomic_snapshot", "whole_file_hashed"});
    metadata(field(receipt, "source_before"));
    metadata(field(receipt, "source_after"));
    if (!same(field(receipt, "source_before"), input.expected_source) ||
        text(receipt, "path") != input.path ||
        text(receipt, "resolved_path") != local_file::utf8(local_file::path_for(input.path)) ||
        text(receipt, "source_identity_digest") != hash(input.expected_source) ||
        text(receipt, "source_consistency") != "live-uncoordinated" ||
        boolean(receipt, "atomic_snapshot") || boolean(receipt, "whole_file_hashed"))
        throw std::invalid_argument("fat_snapshot_source");
    const auto &observation = field(result, "observation");
    const auto serial = integer(observation, "capture_epoch");
    if (!serial)
        throw std::invalid_argument("fat_snapshot_sequence");
    const auto domain = V::object()
                            .put("process", field(frame, "process_id"))
                            .put("process_created", field(frame, "process_created"))
                            .put("sequence", number(serial))
                            .put("source", input.expected_source);
    if (text(receipt, "capture_domain") != hash(domain))
        throw std::invalid_argument("fat_snapshot_domain");
    const auto &source_regions = field(frame, "regions");
    const auto &manifest = field(receipt, "regions");
    if (source_regions.kind != V::Kind::array || manifest.kind != V::Kind::array ||
        source_regions.items.size() > input.limits.read_requests ||
        source_regions.items.size() != manifest.items.size())
        throw std::invalid_argument("fat_snapshot_regions");
    std::vector<FatFileRegion> regions;
    std::set<std::pair<std::uint64_t, std::size_t>> ranges;
    std::size_t requested_bytes = 0, reread_bytes = 0;
    bool overlap = true, equal = true;
    const auto size = integer(input.expected_source, "bytes");
    for (std::size_t i = 0; i < source_regions.items.size(); ++i) {
        const auto &row = source_regions.items[i];
        exact(row, {"offset", "requested", "error", "bytes"});
        const auto at = integer(row, "offset"), want = integer(row, "requested"),
                   error = integer(row, "error");
        if (!want || want > 4096 || error > 0xffffffffULL || at < input.volume_offset ||
            at > size || want > size - at || at - input.volume_offset > input.volume_bytes ||
            want > input.volume_bytes - (at - input.volume_offset))
            throw std::invalid_argument("fat_snapshot_extent");
        FatFileRegion r{at, static_cast<std::size_t>(want), static_cast<std::uint32_t>(error),
                        unhex(text(row, "bytes"), static_cast<std::size_t>(want))};
        if (error && !r.bytes.empty())
            throw std::invalid_argument("fat_snapshot_region_error");
        if (!ranges.insert({at, r.requested}).second ||
            want > input.limits.read_bytes - requested_bytes)
            throw std::invalid_argument("fat_snapshot_region_budget");
        requested_bytes += r.requested;
        const auto &m = manifest.items[i];
        exact(m, {"source_offset", "requested_bytes", "captured_bytes", "sha256", "reread_sha256",
                  "reread_bytes", "error", "reread_error", "matches"});
        if (integer(m, "source_offset") != at || integer(m, "requested_bytes") != want ||
            integer(m, "captured_bytes") != r.bytes.size() || integer(m, "error") != error ||
            text(m, "sha256") != hash(r.bytes.data(), r.bytes.size()))
            throw std::invalid_argument("fat_snapshot_region_binding");
        const auto again = integer(m, "reread_bytes"), again_error = integer(m, "reread_error");
        if (again > want || again_error > 0xffffffffULL || !digest(text(m, "reread_sha256")) ||
            (again_error && (again || text(m, "reread_sha256") != hash(nullptr, 0))))
            throw std::invalid_argument("fat_snapshot_reread");
        if (!again && text(m, "reread_sha256") != hash(nullptr, 0))
            throw std::invalid_argument("fat_snapshot_reread");
        const bool matches = !error && !again_error && r.bytes.size() == want && again == want &&
                             text(m, "sha256") == text(m, "reread_sha256");
        if (boolean(m, "matches") != matches)
            throw std::invalid_argument("fat_snapshot_reread");
        equal = equal && matches;
        reread_bytes += static_cast<std::size_t>(again);
        for (const auto &prior : regions) {
            const auto first = std::max(at, prior.offset),
                       last = std::min(at + r.bytes.size(), prior.offset + prior.bytes.size());
            if (first < last &&
                !std::equal(r.bytes.begin() + static_cast<std::size_t>(first - at),
                            r.bytes.begin() + static_cast<std::size_t>(last - at),
                            prior.bytes.begin() + static_cast<std::size_t>(first - prior.offset)))
                overlap = false;
        }
        regions.push_back(std::move(r));
    }
    equal = equal && overlap;
    const bool metadata_equal =
        same(field(receipt, "source_before"), field(receipt, "source_after"));
    const bool stable = !regions.empty() && equal && metadata_equal;
    if (boolean(receipt, "metadata_equal") != metadata_equal ||
        boolean(receipt, "overlaps_equal") != overlap ||
        boolean(receipt, "regions_equal") != equal ||
        boolean(receipt, "observed_stable") != stable ||
        integer(receipt, "reread_bytes") != reread_bytes)
        throw std::invalid_argument("fat_snapshot_consistency");
    FatNameConsumer consumer;
    if (input.name_code_page)
        consumer = windows_fat_name_consumer(input.name_code_page);
    auto request = capture_request(input, input.name_code_page ? &consumer : nullptr, serial);
    std::size_t next = 0;
    bool sequence_valid = true;
    auto reconstructed = observe_fat_volume(request, [&](const de_byte_extent &e) {
        const auto first = native(e.start), last = native(e.end);
        if (next == regions.size() || last < first || regions[next].offset != first ||
            regions[next].requested != last - first) {
            sequence_valid = false;
            throw std::invalid_argument("fat_snapshot_region_sequence");
        }
        const auto &r = regions[next++];
        return de_view{r.bytes.data(), r.bytes.size()};
    });
    if (!sequence_valid || next != regions.size())
        throw std::invalid_argument("fat_snapshot_region_sequence");
    if (input.name_code_page && !stable)
        withdraw_fat_namespace_applicability(reconstructed.fields.at("namespace"),
                                             "file_recapture_not_applicable");
    if (!stable && reconstructed.find("allocation_window"))
        withdraw_fat_allocation_window_applicability(reconstructed.fields.at("allocation_window"));
    if (!same(reconstructed, observation))
        throw std::invalid_argument("fat_snapshot_reconstruction");
    if (input.content_enabled) {
        const auto &content = field(result, "content");
        exact(content, {"schema", "request", "metadata_digest", "source_before", "source_after",
                        "window", "payload_rereads", "metadata_rereads", "payload_equal",
                        "metadata_equal", "source_equal", "source_consistency",
                        "source_freshness_verified", "atomic_snapshot", "observed_stable"});
        if (!stable || text(content, "schema") != "org.disked.fat-held-content/1" ||
            !same(field(content, "request"), fat_file_content_request_value(input.content)) ||
            text(content, "metadata_digest") != input.content.metadata_digest ||
            fat_content_metadata_digest(reconstructed) != input.content.metadata_digest ||
            !same(field(content, "source_before"), input.expected_source) ||
            text(content, "source_consistency") != "live-uncoordinated" ||
            boolean(content, "source_freshness_verified") || boolean(content, "atomic_snapshot"))
            throw std::invalid_argument("fat_content_snapshot_binding");
        metadata(field(content, "source_after"));
        const auto &payload_rows = field(frame, "content_regions");
        if (payload_rows.kind != V::Kind::array ||
            payload_rows.items.size() > input.content.limits.read_requests)
            throw std::invalid_argument("fat_content_snapshot_budget");
        std::vector<FatFileRegion> payload;
        std::size_t requested = 0;
        for (const auto &row : payload_rows.items) {
            exact(row, {"offset", "requested", "error", "bytes"});
            const auto at = integer(row, "offset"), want = integer(row, "requested"),
                       error = integer(row, "error");
            if (!want || want > input.content.limits.read_chunk || error > 0xffffffffULL ||
                at < input.volume_offset || at > size || want > size - at ||
                at - input.volume_offset > input.volume_bytes ||
                want > input.volume_bytes - (at - input.volume_offset) ||
                want > input.content.limits.bytes - requested)
                throw std::invalid_argument("fat_content_snapshot_extent");
            requested += static_cast<std::size_t>(want);
            auto bytes = unhex(text(row, "bytes"), static_cast<std::size_t>(want));
            if (error && !bytes.empty())
                throw std::invalid_argument("fat_content_snapshot_read");
            payload.push_back({at, static_cast<std::size_t>(want),
                               static_cast<std::uint32_t>(error), std::move(bytes)});
        }
        auto map = prepare_fat_content(reconstructed, input.content.node_id,
                                       {hash(input.expected_source), serial, size,
                                        input.volume_offset, input.volume_bytes, input.fat_copy});
        if (map.file_bytes() != input.content.expected_file_bytes)
            throw std::invalid_argument("fat_content_snapshot_size");
        std::size_t used = 0;
        bool ordered = true;
        auto window = map.read(
            input.content.offset, input.content.count,
            [&](const de_byte_extent &range) {
                const auto at = native(range.start), end = native(range.end);
                if (used == payload.size() || end < at || payload[used].offset != at ||
                    payload[used].requested != end - at) {
                    ordered = false;
                    throw std::invalid_argument("fat_content_snapshot_order");
                }
                const auto &r = payload[used++];
                if (r.error)
                    throw std::runtime_error("recorded content reader error");
                return de_view{r.bytes.data(), r.bytes.size()};
            },
            input.content.limits);
        if (!ordered || used != payload.size() ||
            json::dump(window, fat_snapshot_json_limits(true)) !=
                json::dump(field(content, "window"), fat_snapshot_json_limits(true)))
            throw std::invalid_argument("fat_content_snapshot_reconstruction");
        auto verify_recap = [&](const std::vector<FatFileRegion> &first, const V &rows) {
            if (rows.kind != V::Kind::array || rows.items.size() != first.size())
                throw std::invalid_argument("fat_content_snapshot_recapture");
            bool all = true;
            for (std::size_t i = 0; i < first.size(); ++i) {
                const auto &r = first[i];
                const auto &m = rows.items[i];
                exact(m, {"source_offset", "requested_bytes", "captured_bytes", "error", "sha256",
                          "reread_bytes", "reread_error", "reread_sha256", "matches"});
                const auto again = integer(m, "reread_bytes"), error = integer(m, "reread_error");
                if (integer(m, "source_offset") != r.offset ||
                    integer(m, "requested_bytes") != r.requested ||
                    integer(m, "captured_bytes") != r.bytes.size() ||
                    integer(m, "error") != r.error ||
                    text(m, "sha256") != hash(r.bytes.data(), r.bytes.size()) ||
                    again > r.requested || error > 0xffffffffULL || (error && again) ||
                    !digest(text(m, "reread_sha256")) ||
                    (!again && text(m, "reread_sha256") != hash(nullptr, 0)))
                    throw std::invalid_argument("fat_content_snapshot_recapture_binding");
                const bool agrees = !r.error && !error && r.bytes.size() == r.requested &&
                                    again == r.requested &&
                                    text(m, "sha256") == text(m, "reread_sha256");
                if (boolean(m, "matches") != agrees)
                    throw std::invalid_argument("fat_content_snapshot_recapture_agreement");
                all = all && agrees;
            }
            return all;
        };
        const bool payload_equal = verify_recap(payload, field(content, "payload_rereads"));
        const bool recaptured_metadata_equal =
            verify_recap(regions, field(content, "metadata_rereads"));
        const bool source_equal =
            same(field(content, "source_before"), field(content, "source_after"));
        if (boolean(content, "payload_equal") != payload_equal ||
            boolean(content, "metadata_equal") != recaptured_metadata_equal ||
            boolean(content, "source_equal") != source_equal ||
            boolean(content, "observed_stable") !=
                (payload_equal && recaptured_metadata_equal && source_equal &&
                 text(window, "outcome") == "complete"))
            throw std::invalid_argument("fat_content_snapshot_applicability");
    }
    return result;
}
} // namespace disked
