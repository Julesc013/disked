#include "exfat_snapshot.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("exfat_snapshot_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("exfat_snapshot_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!json::decimal_u64(s))
        throw std::invalid_argument("exfat_snapshot_integer");
    return std::stoull(s);
}
bool boolean(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::boolean)
        throw std::invalid_argument("exfat_snapshot_shape");
    return p.boolean;
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
void exact(const V &v, const std::set<std::string> &keys) {
    if (v.kind != V::Kind::object || v.fields.size() != keys.size())
        throw std::invalid_argument("exfat_snapshot_shape");
    for (const auto &p : v.fields)
        if (!keys.count(p.first))
            throw std::invalid_argument("exfat_snapshot_shape");
}
std::string encode(const V &value) {
    return json::dump(value, exfat_snapshot_json_limits());
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
        throw std::invalid_argument("exfat_snapshot_bytes");
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
        throw std::invalid_argument("exfat_snapshot_metadata");
    const auto created = text(v, "created");
    if (created.size() > 20 || std::to_string(std::stoll(created)) != created)
        throw std::invalid_argument("exfat_snapshot_metadata");
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
        throw std::invalid_argument("exfat_snapshot_metadata");
    for (const auto key : {"written", "changed"}) {
        const auto s = text(v, key);
        if (s.size() > 20 || std::to_string(std::stoll(s)) != s)
            throw std::invalid_argument("exfat_snapshot_metadata");
    }
}
ExfatCaptureRequest capture_request(const ExfatSnapshotInput &input, std::uint64_t sequence = 1) {
    ExfatCaptureRequest request;
    request.source_id = hash(input.expected_source);
    request.epoch = sequence;
    request.source_bytes = integer(input.expected_source, "bytes");
    request.volume_offset = input.volume_offset;
    request.volume_bytes = input.volume_bytes;
    request.upcase_format = input.upcase_format;
    request.limits = input.limits;
    return request;
}
V limit_value(const ExfatCaptureLimits &limits) {
    auto out = V::object();
#define SAVE_LIMIT(name) out.put(#name, number(limits.name))
    SAVE_LIMIT(read_requests);
    SAVE_LIMIT(read_bytes);
    SAVE_LIMIT(clusters);
    SAVE_LIMIT(records);
    SAVE_LIMIT(retained_bytes);
    SAVE_LIMIT(output_bytes);
#undef SAVE_LIMIT
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::invalid_argument("exfat_snapshot_extent");
    return std::stoull(text);
}
} // namespace
json::Limits exfat_snapshot_json_limits() {
    json::Limits limits;
    limits.bytes = exfat_snapshot_payload_bytes;
    limits.values = 524288;
    limits.depth = 48;
    limits.string_bytes = 6291456;
    return limits;
}
V exfat_snapshot_claims() {
    return V::object()
        .put("physical_admission", V::boolean_value(false))
        .put("mutation_authority", V::boolean_value(false))
        .put("atomic_snapshot", V::boolean_value(false))
        .put("storage_consumer_qualified", V::boolean_value(false))
        .put("product_dispatch_admitted", V::boolean_value(false));
}
void validate_exfat_snapshot_input(const ExfatSnapshotInput &input) {
    if (!input.capture_epoch)
        throw std::invalid_argument("exfat_snapshot_input");
    local_file::path_for(input.path);
    metadata(input.expected_source);
    const auto size = integer(input.expected_source, "bytes");
    if (input.volume_offset > size || input.volume_bytes > size - input.volume_offset)
        throw std::invalid_argument("exfat_snapshot_window");
    validate_exfat_capture_request(capture_request(input));
    if (input.fixture.kind != V::Kind::object)
        throw std::invalid_argument("exfat_snapshot_fixture");
    for (const auto &p : input.fixture.fields) {
#ifdef DISKED_EXFAT_WORKER_TESTING
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
            "short", "error", "changed", "metadata", "replay_bytes", "replay_offset", "binding"};
        const std::set<std::string> startups = {"before_spawn", "after_spawn", "after_spawn_alloc"};
        const std::set<std::string> replies = {
            "capture", "worker",  "code",  "request", "scope",  "host",   "observer", "attempt",
            "pid",     "created", "shape", "status",  "claims", "schema", "digest",   "hold"};
        if (p.second.kind != V::Kind::string ||
            (p.first != "worker_fault" && p.first != "capture_fault" &&
             p.first != "startup_fault" && p.first != "reply_fault"))
            throw std::invalid_argument("exfat_snapshot_fixture");
        const auto &choices = p.first == "worker_fault"    ? workers
                              : p.first == "capture_fault" ? captures
                              : p.first == "startup_fault" ? startups
                                                           : replies;
        if (!choices.count(p.second.text))
            throw std::invalid_argument("exfat_snapshot_fixture");
#else
        (void)p;
        throw std::invalid_argument("exfat_snapshot_fixture");
#endif
    }
}
V exfat_snapshot_input_value(const ExfatSnapshotInput &input) {
    validate_exfat_snapshot_input(input);
    return V::object()
        .put("schema", V::string("org.disked.exfat-source-request/2"))
        .put("path", V::string(input.path))
        .put("expected_source", input.expected_source)
        .put("volume_offset", number(input.volume_offset))
        .put("volume_bytes", number(input.volume_bytes))
        .put("upcase_format", V::string(exfat_upcase_format_name(input.upcase_format)))
        .put("limits", limit_value(input.limits))
        .put("fixture", input.fixture);
}
ExfatSnapshotInput exfat_snapshot_input_from(const V &header) {
    ExfatSnapshotInput input;
    input.capture_epoch = integer(header, "capture_epoch");
    exact(field(header, "policy"), {});
    const auto &v = field(header, "provider_input");
    std::set<std::string> keys = {"schema",        "path",         "expected_source",
                                  "volume_offset", "volume_bytes", "upcase_format",
                                  "limits",        "fixture"};
    for (const auto key : {"startup_fault", "reply_fault"})
        if (v.find(key))
            keys.insert(key);
    exact(v, keys);
    if (text(v, "schema") != "org.disked.exfat-source-request/2")
        throw std::invalid_argument("exfat_snapshot_schema");
    input.path = text(v, "path");
    input.expected_source = field(v, "expected_source");
    input.volume_offset = integer(v, "volume_offset");
    input.volume_bytes = integer(v, "volume_bytes");
    input.upcase_format = exfat_upcase_format_from(text(v, "upcase_format"));
    input.fixture = field(v, "fixture");
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *value = v.find(key))
            if (!input.fixture.find(key) || !same(*value, field(input.fixture, key)))
                throw std::invalid_argument("exfat_snapshot_fixture");
    const auto &limits = field(v, "limits");
    exact(limits,
          {"read_requests", "read_bytes", "clusters", "records", "retained_bytes", "output_bytes"});
#define LOAD_LIMIT(name)                                                                           \
    {                                                                                              \
        const auto n = integer(limits, #name);                                                     \
        if (n > 2097152)                                                                           \
            throw std::invalid_argument("exfat_snapshot_limit");                                   \
        input.limits.name = static_cast<std::size_t>(n);                                           \
    }
    LOAD_LIMIT(read_requests);
    LOAD_LIMIT(read_bytes);
    LOAD_LIMIT(clusters);
    LOAD_LIMIT(records);
    LOAD_LIMIT(retained_bytes);
    LOAD_LIMIT(output_bytes);
#undef LOAD_LIMIT
    validate_exfat_snapshot_input(input);
    return input;
}
V read_exfat_snapshot_frame(const ExfatSnapshotInput &input, const std::function<bool()> &stop) {
    validate_exfat_snapshot_input(input);
#ifdef DISKED_EXFAT_WORKER_TESTING
    ExfatFileTestControl control;
    const auto *fault = input.fixture.find("capture_fault");
    const auto mode = fault ? fault->text : "";
    control.after_read = [mode](std::size_t n, ExfatFileRegion &r) {
        if (n != 2)
            return;
        if (mode == "short" && !r.bytes.empty())
            r.bytes.pop_back();
        if (mode == "error") {
            r.error = ERROR_READ_FAULT;
            r.bytes.clear();
        }
        if (mode == "changed" && !r.bytes.empty())
            r.bytes[0] ^= 1;
    };
    control.after_metadata = [mode](V &v) {
        if (mode == "metadata")
            v.put("written", V::string("1"));
    };
    control.before_replay = [mode](std::size_t n, ExfatFileRegion &r) {
        if (n == 1 && mode == "replay_bytes" && !r.bytes.empty())
            r.bytes[0] ^= 1;
        if (n == 1 && mode == "replay_offset")
            ++r.offset;
    };
    control.before_binding = [mode](std::size_t n) {
        if (n == 3 && mode == "binding")
            throw local_file::Error("test_binding_failure", ERROR_INVALID_HANDLE);
    };
    auto captured = capture_exfat_file_testing(input.path, input.volume_offset, input.volume_bytes,
                                               input.upcase_format, input.limits, stop, control,
                                               &input.expected_source);
#else
    auto captured =
        capture_exfat_file_owned(input.path, input.volume_offset, input.volume_bytes,
                                 input.upcase_format, input.limits, stop, &input.expected_source);
#endif
    if (!same(field(field(captured.result, "capture"), "source_before"), input.expected_source))
        throw local_file::Error("exfat_snapshot_source_changed");
    auto regions = V::array();
    for (const auto &r : captured.regions)
        regions.items.push_back(V::object()
                                    .put("offset", number(r.offset))
                                    .put("requested", number(r.requested))
                                    .put("error", number(r.error))
                                    .put("read_attempted", V::boolean_value(r.read_attempted))
                                    .put("refusal", V::string(r.refusal))
                                    .put("bytes", V::string(hex(r.bytes))));
    auto out = V::object()
                   .put("schema", V::string("org.disked.exfat-region-frame/2"))
                   .put("input", exfat_snapshot_input_value(input))
                   .put("capture_epoch", number(input.capture_epoch))
                   .put("process_id", number(captured.process_id))
                   .put("process_created", number(captured.process_created))
                   .put("result", std::move(captured.result))
                   .put("regions", std::move(regions));
    encode(out);
    return out;
}
V verify_exfat_snapshot_frame(const V &frame, const ExfatSnapshotInput &input) {
    validate_exfat_snapshot_input(input);
    exact(frame, {"schema", "input", "capture_epoch", "process_id", "process_created", "result",
                  "regions"});
    encode(frame);
    if (text(frame, "schema") != "org.disked.exfat-region-frame/2" ||
        !same(field(frame, "input"), exfat_snapshot_input_value(input)) ||
        integer(frame, "capture_epoch") != input.capture_epoch || !integer(frame, "process_id") ||
        integer(frame, "process_id") > 0xffffffffULL || !integer(frame, "process_created"))
        throw std::invalid_argument("exfat_snapshot_binding");
    const auto &result = field(frame, "result");
    exact(result,
          {"schema", "observation", "capture", "authorizes_effects", "product_dispatch_admitted"});
    if (text(result, "schema") != "org.disked.exfat-file-capture/2" ||
        boolean(result, "authorizes_effects") || boolean(result, "product_dispatch_admitted"))
        throw std::invalid_argument("exfat_snapshot_claims");
    const auto &receipt = field(result, "capture");
    exact(receipt, {"source_before", "source_after", "parent_generations", "metadata_equal",
                    "source_identity_digest", "observed_stable", "binding_checks_ok",
                    "binding_checks", "binding_error", "binding_platform_error", "replay_equal",
                    "process_id", "process_created", "sequence", "capture_domain",
                    "source_consistency", "atomic_snapshot"});
    metadata(field(receipt, "source_before"));
    if (!same(field(receipt, "source_before"), input.expected_source) ||
        text(receipt, "source_identity_digest") != hash(input.expected_source) ||
        text(receipt, "source_consistency") != "live-uncoordinated" ||
        boolean(receipt, "atomic_snapshot") ||
        integer(receipt, "process_id") != integer(frame, "process_id") ||
        integer(receipt, "process_created") != integer(frame, "process_created"))
        throw std::invalid_argument("exfat_snapshot_source");
    const auto &after = field(receipt, "source_after");
    if (after.kind != V::Kind::null)
        metadata(after);
    const auto &parents = field(receipt, "parent_generations");
    if (parents.kind != V::Kind::array || parents.items.empty() || parents.items.size() > 128)
        throw std::invalid_argument("exfat_snapshot_parents");
    for (const auto &parent : parents.items) {
        exact(parent, {"volume_id", "file_id", "created"});
        generation(parent);
    }
    const auto serial = integer(receipt, "sequence");
    if (!serial || text(receipt, "capture_domain") !=
                       hash(V::object()
                                .put("provider", V::string("exfat-file-prototype"))
                                .put("process_id", field(frame, "process_id"))
                                .put("process_created", field(frame, "process_created"))
                                .put("sequence", number(serial))
                                .put("source", input.expected_source)))
        throw std::invalid_argument("exfat_snapshot_domain");
    const auto &rows = field(frame, "regions");
    if (rows.kind != V::Kind::array || rows.items.size() > input.limits.read_requests)
        throw std::invalid_argument("exfat_snapshot_regions");
    std::vector<ExfatFileRegion> regions;
    std::size_t requested_bytes = 0;
    const auto size = integer(input.expected_source, "bytes");
    for (const auto &row : rows.items) {
        exact(row, {"offset", "requested", "error", "read_attempted", "refusal", "bytes"});
        const auto at = integer(row, "offset"), want = integer(row, "requested"),
                   error = integer(row, "error");
        if (!want || want > 49152 || error > 0xffffffffULL || at < input.volume_offset ||
            at > size || want > size - at || at - input.volume_offset > input.volume_bytes ||
            want > input.volume_bytes - (at - input.volume_offset) ||
            want > input.limits.read_bytes - requested_bytes)
            throw std::invalid_argument("exfat_snapshot_extent");
        ExfatFileRegion r;
        r.offset = at;
        r.requested = static_cast<std::size_t>(want);
        r.error = static_cast<std::uint32_t>(error);
        r.read_attempted = boolean(row, "read_attempted");
        r.refusal = text(row, "refusal");
        r.bytes = unhex(text(row, "bytes"), r.requested);
        if (r.refusal.size() > 128 || r.refusal.find('\0') != r.refusal.npos ||
            !json::valid_utf8(r.refusal) ||
            (!r.read_attempted && (r.refusal.empty() || !r.bytes.empty())) ||
            (r.error && r.refusal.empty() && !r.bytes.empty()))
            throw std::invalid_argument("exfat_snapshot_region_error");
        requested_bytes += r.requested;
        regions.push_back(std::move(r));
    }
    std::size_t next = 0;
    bool ordered = true;
    auto reconstructed =
        observe_exfat_volume(capture_request(input, serial), [&](const de_byte_extent &extent) {
            const auto start = native(extent.start), end = native(extent.end);
            if (next == regions.size() || end < start || regions[next].offset != start ||
                regions[next].requested != end - start) {
                ordered = false;
                throw std::invalid_argument("exfat_snapshot_region_sequence");
            }
            const auto &r = regions[next++];
            if (!r.refusal.empty())
                throw local_file::Error(r.refusal.c_str(), r.error);
            if (r.error)
                throw local_file::Error("exfat_snapshot_read", r.error);
            return de_view{r.bytes.data(), r.bytes.size()};
        });
    if (!ordered || next != regions.size())
        throw std::invalid_argument("exfat_snapshot_region_sequence");
    const bool metadata_equal = same(input.expected_source, after),
               binding_ok = boolean(receipt, "binding_checks_ok");
    const auto checks = integer(receipt, "binding_checks"),
               platform = integer(receipt, "binding_platform_error");
    const auto binding_error = text(receipt, "binding_error");
    if (checks < regions.size() + 2 || checks > regions.size() + 3 || platform > 0xffffffffULL ||
        binding_error.size() > 128 || binding_error.find('\0') != binding_error.npos ||
        !json::valid_utf8(binding_error) ||
        (binding_ok && (after.kind != V::Kind::object || !binding_error.empty() || platform)) ||
        (!binding_ok && binding_error.empty()) ||
        boolean(receipt, "metadata_equal") != metadata_equal || !boolean(receipt, "replay_equal"))
        throw std::invalid_argument("exfat_snapshot_consistency");
    const bool stable = metadata_equal && binding_ok && boolean(reconstructed, "applicable");
    if (!metadata_equal || !binding_ok) {
        reconstructed.put("applicable", V::boolean_value(false));
        reconstructed.fields.at("diagnostics")
            .items.push_back(V::string("exfat_file_binding_disagreement"));
    }
    if (boolean(receipt, "observed_stable") != stable ||
        !same(reconstructed, field(result, "observation")))
        throw std::invalid_argument("exfat_snapshot_reconstruction");
    return result;
}
} // namespace disked
