#include "ntfs_snapshot.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("ntfs_snapshot_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("ntfs_snapshot_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw std::invalid_argument("ntfs_snapshot_integer");
    return std::stoull(s);
}
bool boolean(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::boolean)
        throw std::invalid_argument("ntfs_snapshot_shape");
    return p.boolean;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        throw std::invalid_argument("ntfs_snapshot_shape");
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            throw std::invalid_argument("ntfs_snapshot_shape");
}
std::string encode(const V &value) {
    return json::dump(value, ntfs_snapshot_json_limits());
}
bool same(const V &a, const V &b) {
    return encode(a) == encode(b);
}
std::string hex(const std::vector<unsigned char> &bytes) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (auto byte : bytes) {
        out += digits[byte >> 4];
        out += digits[byte & 15];
    }
    return out;
}
std::string hash(const V &value) {
    const auto bytes = encode(value);
    unsigned char out[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), out);
    return "sha256:" + hex(std::vector<unsigned char>(out, out + 32));
}
std::vector<unsigned char> unhex(const std::string &s, std::size_t maximum) {
    if (s.size() % 2 || s.size() / 2 > maximum || s.find_first_not_of("0123456789abcdef") != s.npos)
        throw std::invalid_argument("ntfs_snapshot_bytes");
    auto digit = [](char c) { return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10); };
    std::vector<unsigned char> out(s.size() / 2);
    for (std::size_t n = 0; n < out.size(); ++n)
        out[n] = static_cast<unsigned char>(digit(s[n * 2]) * 16 + digit(s[n * 2 + 1]));
    return out;
}
void generation(const V &v) {
    integer(v, "volume_id");
    const auto id = text(v, "file_id");
    if (id.size() != 32 || id.find_first_not_of("0123456789abcdef") != id.npos)
        throw std::invalid_argument("ntfs_snapshot_metadata");
    const auto created = text(v, "created");
    if (created.size() > 20 || std::to_string(std::stoll(created)) != created)
        throw std::invalid_argument("ntfs_snapshot_metadata");
}
void metadata(const V &v) {
    exact(v, {"volume_id", "file_id", "bytes", "created", "written", "changed", "attributes",
              "hardlinks"});
    generation(v);
    const auto attributes = integer(v, "attributes");
    if (integer(v, "bytes") > static_cast<std::uint64_t>(MAXLONGLONG) ||
        attributes > 0xffffffffULL ||
        attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT |
                      FILE_ATTRIBUTE_OFFLINE | 0x00040000U | 0x00400000U) ||
        integer(v, "hardlinks") != 1)
        throw std::invalid_argument("ntfs_snapshot_metadata");
    for (const auto key : {"written", "changed"}) {
        const auto s = text(v, key);
        if (s.size() > 20 || std::to_string(std::stoll(s)) != s)
            throw std::invalid_argument("ntfs_snapshot_metadata");
    }
}
const char *profile_name(NtfsFileProfile p) {
    switch (p) {
    case NtfsFileProfile::Automatic:
        return "auto";
    case NtfsFileProfile::Version30:
        return "3.0";
    case NtfsFileProfile::Version31:
        return "3.1";
    }
    throw std::invalid_argument("ntfs_snapshot_profile");
}
V limit_value(const NtfsCaptureLimits &l) {
    auto v = V::object();
#define SAVE(n) v.put(#n, number(l.n))
    SAVE(read_requests);
    SAVE(read_bytes);
    SAVE(retained_bytes);
    SAVE(attributes);
    SAVE(runs);
    SAVE(output_bytes);
#undef SAVE
    return v;
}
NtfsCaptureRequest capture_request(const NtfsSnapshotInput &input, std::uint64_t serial = 1) {
    NtfsCaptureRequest r;
    r.source_id = hash(input.expected_source);
    r.source_bytes = integer(input.expected_source, "bytes");
    r.epoch = serial;
    r.volume_offset = input.volume_offset;
    r.volume_bytes = input.volume_bytes;
    r.minor = input.profile == NtfsFileProfile::Version30 ? 0 : 1;
    r.limits = input.limits;
    return r;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::invalid_argument("ntfs_snapshot_extent");
    return std::stoull(text);
}
bool version(const V &v, const char *minor) {
    const auto *info = v.find("volume_information");
    const auto *a = info ? info->find("major") : nullptr;
    const auto *b = info ? info->find("minor") : nullptr;
    return a && b && a->kind == V::Kind::string && b->kind == V::Kind::string && a->text == "3" &&
           b->text == minor;
}
void diagnostic(const std::string &s) {
    if (s.size() > 128 || s.find('\0') != s.npos || !json::valid_utf8(s))
        throw std::invalid_argument("ntfs_snapshot_diagnostic");
}
} // namespace
json::Limits ntfs_snapshot_json_limits() {
    json::Limits l;
    l.bytes = ntfs_snapshot_payload_bytes;
    l.values = 524288;
    l.depth = 48;
    l.string_bytes = 6291456;
    return l;
}
V ntfs_snapshot_claims() {
    return V::object()
        .put("physical_admission", V::boolean_value(false))
        .put("mutation_authority", V::boolean_value(false))
        .put("atomic_snapshot", V::boolean_value(false))
        .put("storage_consumer_qualified", V::boolean_value(false))
        .put("product_dispatch_admitted", V::boolean_value(false));
}
void validate_ntfs_snapshot_input(const NtfsSnapshotInput &input) {
    if (!input.capture_epoch)
        throw std::invalid_argument("ntfs_snapshot_epoch");
    profile_name(input.profile);
    local_file::path_for(input.path);
    metadata(input.expected_source);
    validate_ntfs_capture_request(capture_request(input));
    if (input.fixture.kind != V::Kind::object)
        throw std::invalid_argument("ntfs_snapshot_fixture");
    for (const auto &p : input.fixture.fields) {
#ifdef DISKED_NTFS_WORKER_TESTING
        const std::set<std::string> workers = {"hang",
                                               "late",
                                               "exit",
                                               "payload_changed",
                                               "result_changed",
                                               "receipt_changed",
                                               "process_changed",
                                               "domain_changed",
                                               "row_changed",
                                               "claims"};
        const std::set<std::string> captures = {
            "short", "error", "changed", "metadata", "binding", "replay_bytes", "replay_offset"};
        const std::set<std::string> startups = {"before_spawn", "after_spawn", "after_spawn_alloc"};
        const std::set<std::string> replies = {
            "capture", "worker",  "code",  "request", "scope",  "host",   "observer", "attempt",
            "pid",     "created", "shape", "status",  "claims", "schema", "digest",   "hold"};
        if (p.second.kind != V::Kind::string)
            throw std::invalid_argument("ntfs_snapshot_fixture");
        const auto *choices = p.first == "worker_fault"    ? &workers
                              : p.first == "capture_fault" ? &captures
                              : p.first == "startup_fault" ? &startups
                              : p.first == "reply_fault"   ? &replies
                                                           : nullptr;
        if (!choices || !choices->count(p.second.text))
            throw std::invalid_argument("ntfs_snapshot_fixture");
#else
        (void)p;
        throw std::invalid_argument("ntfs_snapshot_fixture");
#endif
    }
}
V ntfs_snapshot_input_value(const NtfsSnapshotInput &input) {
    validate_ntfs_snapshot_input(input);
    return V::object()
        .put("schema", V::string("org.disked.ntfs-source-request/1"))
        .put("path", V::string(input.path))
        .put("expected_source", input.expected_source)
        .put("volume_offset", number(input.volume_offset))
        .put("volume_bytes", number(input.volume_bytes))
        .put("profile", V::string(profile_name(input.profile)))
        .put("limits", limit_value(input.limits))
        .put("fixture", input.fixture);
}
NtfsSnapshotInput ntfs_snapshot_input_from(const V &h) {
    NtfsSnapshotInput input;
    input.capture_epoch = integer(h, "capture_epoch");
    exact(field(h, "policy"), {});
    const auto &v = field(h, "provider_input");
    std::set<std::string> keys = {"schema",       "path",    "expected_source", "volume_offset",
                                  "volume_bytes", "profile", "limits",          "fixture"};
    for (const auto k : {"startup_fault", "reply_fault"})
        if (v.find(k))
            keys.insert(k);
    exact(v, keys);
    if (text(v, "schema") != "org.disked.ntfs-source-request/1")
        throw std::invalid_argument("ntfs_snapshot_schema");
    input.path = text(v, "path");
    input.expected_source = field(v, "expected_source");
    input.volume_offset = integer(v, "volume_offset");
    input.volume_bytes = integer(v, "volume_bytes");
    const auto selected = text(v, "profile");
    if (selected == "3.0")
        input.profile = NtfsFileProfile::Version30;
    else if (selected == "3.1")
        input.profile = NtfsFileProfile::Version31;
    else if (selected != "auto")
        throw std::invalid_argument("ntfs_snapshot_profile");
    input.fixture = field(v, "fixture");
    for (const auto k : {"startup_fault", "reply_fault"})
        if (const auto *p = v.find(k))
            if (!input.fixture.find(k) || !same(*p, field(input.fixture, k)))
                throw std::invalid_argument("ntfs_snapshot_fixture");
    const auto &l = field(v, "limits");
    exact(l,
          {"read_requests", "read_bytes", "retained_bytes", "attributes", "runs", "output_bytes"});
#define LOAD(n)                                                                                    \
    {                                                                                              \
        const auto x = integer(l, #n);                                                             \
        if (x > 2097152)                                                                           \
            throw std::invalid_argument("ntfs_snapshot_limit");                                    \
        input.limits.n = static_cast<std::size_t>(x);                                              \
    }
    LOAD(read_requests);
    LOAD(read_bytes);
    LOAD(retained_bytes);
    LOAD(attributes);
    LOAD(runs);
    LOAD(output_bytes);
#undef LOAD
    validate_ntfs_snapshot_input(input);
    return input;
}
V read_ntfs_snapshot_frame(const NtfsSnapshotInput &input, const std::function<bool()> &stop) {
    const auto held = input;
    const auto selected_stop = stop;
    validate_ntfs_snapshot_input(held);
    NtfsFileRequest r;
    r.path = held.path;
    r.expected_source = held.expected_source;
    r.volume_offset = held.volume_offset;
    r.volume_bytes = held.volume_bytes;
    r.profile = held.profile;
    r.limits = held.limits;
#ifdef DISKED_NTFS_WORKER_TESTING
    NtfsFileTestControl control;
    const auto *f = held.fixture.find("capture_fault");
    const auto mode = f ? f->text : "";
    control.after_read = [mode](std::size_t n, NtfsFileRegion &row) {
        if (n != 2)
            return;
        if (mode == "short" && !row.bytes.empty())
            row.bytes.pop_back();
        if (mode == "error") {
            row.error = ERROR_READ_FAULT;
            row.bytes.clear();
        }
        if (mode == "changed" && !row.bytes.empty())
            row.bytes[0] ^= 1;
    };
    control.after_metadata = [mode](V &v) {
        if (mode == "metadata")
            v.put("written", V::string("1"));
    };
    control.before_binding = [mode](std::size_t n) {
        if (n == 3 && mode == "binding")
            throw local_file::Error("test_binding_failure", ERROR_INVALID_HANDLE);
    };
    control.before_replay = [mode](std::size_t n, NtfsFileRegion &row) {
        if (n == 1 && mode == "replay_bytes" && !row.bytes.empty())
            row.bytes[0] ^= 1;
        if (n == 1 && mode == "replay_offset")
            ++row.offset;
    };
    auto read = capture_ntfs_file_testing(r, selected_stop, control);
#else
    auto read = capture_ntfs_file_owned(r, selected_stop);
#endif
    const auto &receipt = field(read.result, "capture");
    auto regions = V::array();
    for (const auto &row : read.regions)
        regions.items.push_back(V::object()
                                    .put("offset", number(row.offset))
                                    .put("requested", number(row.requested))
                                    .put("error", number(row.error))
                                    .put("seek_attempted", V::boolean_value(row.seek_attempted))
                                    .put("read_attempted", V::boolean_value(row.read_attempted))
                                    .put("refusal", V::string(row.refusal))
                                    .put("bytes", V::string(hex(row.bytes))));
    const auto pid = field(receipt, "process_id"), created = field(receipt, "process_created");
    auto out = V::object()
                   .put("schema", V::string("org.disked.ntfs-region-frame/1"))
                   .put("input", ntfs_snapshot_input_value(held))
                   .put("capture_epoch", number(held.capture_epoch))
                   .put("process_id", pid)
                   .put("process_created", created)
                   .put("result", std::move(read.result))
                   .put("regions", std::move(regions));
    encode(out);
    return out;
}
V verify_ntfs_snapshot_frame(const V &frame, const NtfsSnapshotInput &input) {
    validate_ntfs_snapshot_input(input);
    encode(frame);
    exact(frame, {"schema", "input", "capture_epoch", "process_id", "process_created", "result",
                  "regions"});
    if (text(frame, "schema") != "org.disked.ntfs-region-frame/1" ||
        !same(field(frame, "input"), ntfs_snapshot_input_value(input)) ||
        integer(frame, "capture_epoch") != input.capture_epoch || !integer(frame, "process_id") ||
        integer(frame, "process_id") > 0xffffffffULL || !integer(frame, "process_created"))
        throw std::invalid_argument("ntfs_snapshot_binding");
    const auto &result = field(frame, "result");
    exact(result,
          {"schema", "observation", "capture", "authorizes_effects", "product_dispatch_admitted"});
    if (text(result, "schema") != "org.disked.ntfs-file-capture/1" ||
        boolean(result, "authorizes_effects") || boolean(result, "product_dispatch_admitted"))
        throw std::invalid_argument("ntfs_snapshot_claims");
    const auto &c = field(result, "capture");
    exact(c, {"source_before",
              "source_after",
              "source_final",
              "parent_generations",
              "source_identity_digest",
              "process_id",
              "process_created",
              "sequence",
              "capture_domain",
              "domain",
              "selector",
              "selected_profile",
              "profile_probe_minor",
              "profile_probe_diagnostic",
              "profile_selection_equal",
              "replay_equal",
              "retained_replays",
              "replay_calls",
              "metadata_complete",
              "metadata_equal",
              "binding_checks_ok",
              "binding_checks",
              "binding_error",
              "binding_platform_error",
              "cancel_observed",
              "observed_stable",
              "atomic_snapshot",
              "source_consistency"});
    metadata(field(c, "source_before"));
    const auto &after = field(c, "source_after"), &final = field(c, "source_final");
    if (after.kind != V::Kind::null)
        metadata(after);
    if (final.kind != V::Kind::null)
        metadata(final);
    if (!same(field(c, "source_before"), input.expected_source) ||
        text(c, "source_identity_digest") != hash(input.expected_source) ||
        integer(c, "process_id") != integer(frame, "process_id") ||
        integer(c, "process_created") != integer(frame, "process_created") ||
        boolean(c, "atomic_snapshot") || text(c, "source_consistency") != "live-uncoordinated")
        throw std::invalid_argument("ntfs_snapshot_source");
    const auto &parents = field(c, "parent_generations");
    if (parents.kind != V::Kind::array || parents.items.empty() || parents.items.size() > 128)
        throw std::invalid_argument("ntfs_snapshot_parents");
    for (const auto &p : parents.items) {
        exact(p, {"volume_id", "file_id", "created"});
        generation(p);
    }
    const auto serial = integer(c, "sequence");
    if (!serial)
        throw std::invalid_argument("ntfs_snapshot_sequence");
    auto request = capture_request(input, serial);
    const auto &rows = field(frame, "regions");
    if (rows.kind != V::Kind::array || rows.items.size() > input.limits.read_requests)
        throw std::invalid_argument("ntfs_snapshot_regions");
    std::vector<NtfsFileRegion> regions;
    std::size_t total = 0;
    for (const auto &row : rows.items) {
        exact(row, {"offset", "requested", "error", "seek_attempted", "read_attempted", "refusal",
                    "bytes"});
        const auto at = integer(row, "offset"), want = integer(row, "requested"),
                   error = integer(row, "error");
        if (!want || want > 49152 || error > 0xffffffffULL || at < input.volume_offset ||
            at - input.volume_offset > input.volume_bytes ||
            want > input.volume_bytes - (at - input.volume_offset) ||
            want > input.limits.read_bytes - total)
            throw std::invalid_argument("ntfs_snapshot_extent");
        NtfsFileRegion r;
        r.offset = at;
        r.requested = static_cast<std::size_t>(want);
        r.error = static_cast<std::uint32_t>(error);
        r.seek_attempted = boolean(row, "seek_attempted");
        r.read_attempted = boolean(row, "read_attempted");
        r.refusal = text(row, "refusal");
        diagnostic(r.refusal);
        r.bytes = unhex(text(row, "bytes"), r.requested);
        if ((!r.seek_attempted && (r.read_attempted || r.refusal.empty())) ||
            (!r.read_attempted && !r.bytes.empty()) ||
            (r.seek_attempted && !r.read_attempted && !r.error && r.refusal.empty()))
            throw std::invalid_argument("ntfs_snapshot_attempts");
        total += r.requested;
        regions.push_back(std::move(r));
    }
    auto replay = [&] {
        std::size_t used = 0;
        bool ordered = true;
        auto observed = observe_ntfs_bootstrap(request, [&](const de_byte_extent &extent) {
            const auto start = native(extent.start), end = native(extent.end);
            if (!extent.space || extent.space->logical_block_bytes != 1 ||
                native(extent.space->blocks) != request.source_bytes ||
                std::string(extent.space->name, extent.space->name_length) != request.source_id ||
                used == regions.size() || end < start || regions[used].offset != start ||
                regions[used].requested != end - start) {
                ordered = false;
                throw std::invalid_argument("ntfs_snapshot_order");
            }
            const auto &r = regions[used++];
            if (!r.refusal.empty())
                throw local_file::Error(r.refusal.c_str(), r.error);
            if (r.error)
                throw local_file::Error("ntfs_snapshot_read", r.error);
            return de_view{r.bytes.data(), r.bytes.size()};
        });
        if (!ordered || used != regions.size())
            throw std::invalid_argument("ntfs_snapshot_order");
        return observed;
    };
    const auto probe = replay();
    auto observed = probe;
    bool selected = input.profile != NtfsFileProfile::Automatic || version(probe, "1");
    std::uint64_t passes = 1;
    if (input.profile == NtfsFileProfile::Automatic && boolean(probe, "complete") &&
        text(probe, "diagnostic") == "ntfs_volume_version" && version(probe, "0")) {
        request.minor = 0;
        observed = replay();
        ++passes;
        auto expected = probe;
        expected.put("requested_minor", number(0))
            .put("applicable", V::boolean_value(true))
            .put("diagnostic", V::string(""));
        expected.fields.at("volume_information").put("profile_matches", V::boolean_value(true));
        if (!same(expected, observed))
            throw std::invalid_argument("ntfs_snapshot_profile_replay");
        selected = true;
    }
    const auto profile = selected ? V::string(request.minor ? "3.1" : "3.0") : V{};
    const auto domain = V::object()
                            .put("provider", V::string("ntfs-file-prototype"))
                            .put("process_id", field(frame, "process_id"))
                            .put("process_created", field(frame, "process_created"))
                            .put("sequence", number(serial))
                            .put("source", input.expected_source)
                            .put("volume_offset", number(input.volume_offset))
                            .put("volume_bytes", number(input.volume_bytes))
                            .put("selector", V::string(profile_name(input.profile)))
                            .put("selected_profile", profile)
                            .put("limits", limit_value(input.limits));
    if (!same(field(c, "domain"), domain) || text(c, "capture_domain") != hash(domain) ||
        text(c, "selector") != profile_name(input.profile) ||
        !same(field(c, "selected_profile"), profile) ||
        !same(field(c, "profile_probe_minor"), field(probe, "requested_minor")) ||
        !same(field(c, "profile_probe_diagnostic"), field(probe, "diagnostic")) ||
        !boolean(c, "profile_selection_equal") || !boolean(c, "replay_equal") ||
        integer(c, "retained_replays") != passes ||
        integer(c, "replay_calls") != regions.size() * passes)
        throw std::invalid_argument("ntfs_snapshot_receipt");
    const bool complete = after.kind == V::Kind::object && final.kind == V::Kind::object;
    const bool equal =
        complete && same(input.expected_source, after) && same(input.expected_source, final);
    const bool binding = boolean(c, "binding_checks_ok"), cancelled = boolean(c, "cancel_observed");
    const auto checks = integer(c, "binding_checks"),
               platform = integer(c, "binding_platform_error");
    const auto error = text(c, "binding_error");
    diagnostic(error);
    if (checks < regions.size() + 3 || checks > 2 * regions.size() + 5 ||
        platform > 0xffffffffULL || boolean(c, "metadata_complete") != complete ||
        boolean(c, "metadata_equal") != equal ||
        (binding && (!complete || !error.empty() || platform || cancelled ||
                     checks != 2 * regions.size() + 5)) ||
        (!binding && error.empty()) || (error == "ntfs_file_cancelled" && !cancelled))
        throw std::invalid_argument("ntfs_snapshot_consistency");
    const bool stable = binding && equal && selected && boolean(observed, "applicable");
    if (!binding || !equal || !selected)
        observed.put("applicable", V::boolean_value(false))
            .put("binding_diagnostic", V::string(!selected ? "ntfs_file_profile_unresolved"
                                                           : "ntfs_file_binding_disagreement"));
    if (boolean(c, "observed_stable") != stable || !same(observed, field(result, "observation")))
        throw std::invalid_argument("ntfs_snapshot_reconstruction");
    return result;
}
} // namespace disked
