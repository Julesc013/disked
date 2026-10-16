#include "ntfs_inspection.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &value, const char *key) {
    const auto *found = value.find(key);
    if (!found)
        throw std::invalid_argument("ntfs_result_shape");
    return *found;
}
bool flag(const V &value, const char *key) {
    const auto &found = field(value, key);
    if (found.kind != V::Kind::boolean)
        throw std::invalid_argument("ntfs_result_shape");
    return found.boolean;
}
std::uint64_t integer(const V &value, const char *key) {
    const auto &found = field(value, key);
    if (found.kind != V::Kind::string || !json::decimal_u64(found.text))
        throw std::invalid_argument("ntfs_result_integer");
    return std::stoull(found.text);
}
V number(std::uint64_t value) {
    return V::string(std::to_string(value));
}
json::Limits full_limits() {
    json::Limits limits;
    limits.bytes = 8U * 1024U * 1024U;
    limits.string_bytes = 6U * 1024U * 1024U;
    limits.values = 524288;
    limits.depth = 48;
    return limits;
}
json::Limits output_limits() {
    auto limits = full_limits();
    limits.bytes = ntfs_inspection_response_bytes - 1; // Include the framing LF.
    limits.values = 65536;
    limits.string_bytes = 32768;
    return limits;
}
std::string digest(const V &value) {
    const auto encoded = json::dump(value, full_limits());
    unsigned char bytes[32];
    sha256(reinterpret_cast<const unsigned char *>(encoded.data()), encoded.size(), bytes);
    const char alphabet[] = "0123456789abcdef";
    std::string result = "sha256:";
    for (auto byte : bytes) {
        result += alphabet[byte >> 4];
        result += alphabet[byte & 15];
    }
    return result;
}
// Hash the original list even when a row has its own nested projection.
V rows(const V &original, const V &projected, std::size_t budget, std::size_t maximum) {
    if (original.kind != V::Kind::array || projected.kind != V::Kind::array ||
        original.items.size() != projected.items.size())
        throw std::invalid_argument("ntfs_result_shape");
    auto returned = V::array();
    std::size_t used = 0;
    for (const auto &row : projected.items) {
        const auto bytes = json::dump(row, full_limits()).size() + 1;
        if (returned.items.size() == maximum || bytes > budget - used)
            break;
        returned.items.push_back(row);
        used += bytes;
    }
    const auto count = returned.items.size();
    return V::object()
        .put("items", std::move(returned))
        .put("total", number(original.items.size()))
        .put("returned", number(count))
        .put("omitted", number(original.items.size() - count))
        .put("sha256", V::string(digest(original)));
}
void project_record(V &record) {
    const auto *original = record.find("attributes");
    if (!original)
        return;
    if (original->kind != V::Kind::array)
        throw std::invalid_argument("ntfs_result_shape");
    auto projected = *original;
    for (auto &attribute : projected.items) {
        if (const auto *runs = attribute.find("runs"))
            attribute.put("runs", rows(*runs, *runs, 8192, 64));
    }
    // Compute the complete replacement before invalidating the original pointer.
    auto replacement = rows(*original, projected, 65536, 128);
    record.put("attributes", std::move(replacement));
}
void project_closures(V &observation) {
    if (!observation.find("record_closures"))
        return;
    auto &closures = observation.fields.at("record_closures");
    if (closures.kind != V::Kind::object)
        throw std::invalid_argument("ntfs_result_shape");
    for (auto &entry : closures.fields) {
        auto &closure = entry.second;
        const auto &extensions = field(closure, "extensions");
        auto projected = extensions;
        for (auto &record : projected.items)
            project_record(record);
        closure.put("extensions", rows(extensions, projected, 65536, 128));
        if (!closure.find("join") || closure.fields.at("join").kind == V::Kind::null)
            continue;
        auto &join = closure.fields.at("join");
        for (const auto *key : {"records", "parts", "runs", "required_records"}) {
            const auto &original = field(join, key);
            const bool small = std::string(key) == "runs" || std::string(key) == "required_records";
            auto replacement = rows(original, original, small ? 8192 : 32768, small ? 64 : 128);
            join.put(key, std::move(replacement));
        }
    }
}
std::string display_name(const V &value) {
    if (value.kind != V::Kind::string || value.text.size() > 1020 || value.text.size() % 4 ||
        value.text.find_first_not_of("0123456789abcdef") != std::string::npos)
        throw std::invalid_argument("ntfs_result_name");
    const char hex[] = "0123456789abcdef";
    auto digit = [&](char c) { return static_cast<unsigned>(std::string(hex).find(c)); };
    std::string result;
    for (std::size_t i = 0; i < value.text.size(); i += 4) {
        const auto unit = (digit(value.text[i]) << 4) | digit(value.text[i + 1]) |
                          (digit(value.text[i + 2]) << 12) | (digit(value.text[i + 3]) << 8);
        if (unit >= 32 && unit < 127) {
            if (unit == '"' || unit == '\\')
                result += '\\';
            result += static_cast<char>(unit);
        } else {
            result += "\\u";
            for (int shift = 12; shift >= 0; shift -= 4)
                result += hex[(unit >> shift) & 15];
        }
    }
    return result;
}
void project_directory(V &observation) {
    project_record(observation.fields.at("directory_record"));
    const auto &queries = field(observation, "directory_stream_queries");
    auto query_rows = rows(queries, queries, 4096, 16);
    observation.put("directory_stream_queries", std::move(query_rows));
    auto &directory = observation.fields.at("directory");
    if (directory.kind == V::Kind::null)
        return; // A legitimate bootstrap refusal never observed a directory.
    if (field(directory, "schema").text != "org.disked.ntfs-index-collection/1")
        throw std::invalid_argument("ntfs_result_shape");
    directory.put("original_schema", field(directory, "schema"))
        .put("schema", V::string("org.disked.ntfs-index-projection/1"))
        .put("name_display_encoding", V::string("escaped-utf16le-code-units/1"));
    const auto &streams = field(directory, "streams");
    auto projected = streams;
    for (auto &stream : projected.items) {
        for (const auto key : {"runs", "parts"}) {
            const auto &original = field(stream, key);
            auto replacement = rows(original, original, std::string(key) == "runs" ? 8192 : 32768,
                                    std::string(key) == "runs" ? 64 : 128);
            stream.put(key, std::move(replacement));
        }
    }
    auto stream_rows = rows(streams, projected, 65536, 16);
    directory.put("streams", std::move(stream_rows));
    const auto &blocks = field(directory, "blocks");
    auto block_rows = rows(blocks, blocks, 65536, 128);
    directory.put("blocks", std::move(block_rows));
    const auto &entries = field(directory, "entries");
    auto named = entries;
    for (auto &entry : named.items)
        if (const auto *name = entry.find("name_hex"))
            entry.put("name_display", V::string(display_name(*name)));
    auto entry_rows = rows(entries, named, 65536, 256);
    directory.put("entries", std::move(entry_rows));
}
void bind_directory_result(const V &file, const NtfsInspectionRequest &request) {
    const auto &observation = field(file, "observation"), &capture = field(file, "capture"),
               &domain = field(capture, "domain");
    const auto version = request.profile == NtfsFileProfile::Automatic   ? "auto"
                         : request.profile == NtfsFileProfile::Version30 ? "3.0"
                                                                         : "3.1";
    if (field(observation, "schema").text != "org.disked.ntfs-directory-observation-prototype/1" ||
        integer(observation, "volume_offset") != request.volume_offset ||
        integer(observation, "volume_bytes") != request.volume_bytes ||
        integer(observation, "requested_directory_reference") != request.directory_reference ||
        integer(domain, "volume_offset") != request.volume_offset ||
        integer(domain, "volume_bytes") != request.volume_bytes ||
        integer(domain, "directory_reference") != request.directory_reference ||
        field(capture, "selector").text != version || field(domain, "selector").text != version)
        throw std::invalid_argument("ntfs_result_binding");
    const auto limits = ntfs_inspection_capture_limits(request.kind);
    const auto &bound = field(domain, "limits");
    if (integer(bound, "read_requests") != limits.read_requests ||
        integer(bound, "read_bytes") != limits.read_bytes ||
        integer(bound, "retained_bytes") != limits.retained_bytes ||
        integer(bound, "attributes") != limits.attributes ||
        integer(bound, "runs") != limits.runs ||
        integer(bound, "output_bytes") != limits.output_bytes)
        throw std::invalid_argument("ntfs_result_binding");
    const auto directory = ntfs_inspection_directory_limits();
    const auto &selected = field(domain, "directory_limits");
    if (integer(selected, "entries") != directory.entries ||
        integer(selected, "blocks") != directory.blocks ||
        integer(selected, "bitmap_bytes") != directory.bitmap_bytes)
        throw std::invalid_argument("ntfs_result_binding");
}
Outcome failure(const std::string &request, const std::string &code, int exit_code) {
    auto out = refused(request, code, exit_code);
    if (exit_code == 4)
        out.response.put("status", V::string("failed"));
    if (exit_code == 6)
        out.response.put("status", V::string("unknown"));
    return out;
}
} // namespace
bool ntfs_inspection_parameters(const V &parameters) {
    const auto *view = parameters.find("view");
    return view && view->kind == V::Kind::string &&
           (view->text == "ntfs" || view->text == "ntfs-directory");
}
NtfsCaptureLimits ntfs_inspection_capture_limits(NtfsSnapshotKind kind) {
    NtfsCaptureLimits limits;
    if (kind == NtfsSnapshotKind::Directory) {
        limits.read_requests = 512;
        limits.read_bytes = 2097152;
        limits.retained_bytes = 524288;
        limits.attributes = limits.runs = 4096;
    } else if (kind != NtfsSnapshotKind::Bootstrap)
        throw std::invalid_argument("ntfs_inspection_kind");
    return limits;
}
NtfsDirectoryLimits ntfs_inspection_directory_limits() {
    return NtfsDirectoryLimits{4096, 128, 65536};
}
void validate_ntfs_inspection_request(const NtfsInspectionRequest &request) {
    if (request.path.empty() || request.path.size() > 32768 ||
        request.path.find('\0') != request.path.npos || !json::valid_utf8(request.path) ||
        request.volume_bytes < 512 || request.volume_offset > 0x7fffffffffffffffULL ||
        request.volume_bytes > 0x7fffffffffffffffULL - request.volume_offset ||
        (request.profile != NtfsFileProfile::Automatic &&
         request.profile != NtfsFileProfile::Version30 &&
         request.profile != NtfsFileProfile::Version31))
        throw std::invalid_argument("ntfs_inspection_input");
    ntfs_inspection_capture_limits(request.kind);
    if ((request.kind == NtfsSnapshotKind::Bootstrap && request.directory_reference) ||
        (request.directory_reference && !(request.directory_reference >> 48)))
        throw std::invalid_argument("ntfs_inspection_reference");
}
bool decode_ntfs_inspection(const V &parameters, NtfsInspectionRequest &result) {
    try {
        if (parameters.kind != V::Kind::object || !ntfs_inspection_parameters(parameters))
            return false;
        const bool directory = field(parameters, "view").text == "ntfs-directory";
        std::set<std::string> keys = {"path", "view", "volume_offset", "volume_bytes",
                                      "ntfs_version"};
        if (directory)
            keys.insert("directory_reference");
        for (const auto &entry : parameters.fields)
            if (!keys.count(entry.first))
                return false;
        const auto &path = field(parameters, "path");
        if (path.kind != V::Kind::string || path.text.empty() || path.text.size() > 32768 ||
            path.text.find('\0') != path.text.npos || !json::valid_utf8(path.text))
            return false;
        NtfsInspectionRequest selected;
        if (directory) {
            selected.kind = NtfsSnapshotKind::Directory;
            if (parameters.find("directory_reference"))
                selected.directory_reference = integer(parameters, "directory_reference");
        }
        selected.path = path.text;
        selected.volume_offset = integer(parameters, "volume_offset");
        selected.volume_bytes = integer(parameters, "volume_bytes");
        const std::uint64_t maximum = 0x7fffffffffffffffULL;
        if (selected.volume_bytes < 512 || selected.volume_offset > maximum ||
            selected.volume_bytes > maximum - selected.volume_offset)
            return false;
        if (const auto *version = parameters.find("ntfs_version")) {
            if (version->kind != V::Kind::string)
                return false;
            if (version->text == "3.0")
                selected.profile = NtfsFileProfile::Version30;
            else if (version->text == "3.1")
                selected.profile = NtfsFileProfile::Version31;
            else if (version->text != "auto")
                return false;
        }
        validate_ntfs_inspection_request(selected);
        result = std::move(selected);
        return true;
    } catch (const std::exception &) {
        return false;
    }
}
V project_ntfs_inspection(const NtfsInspectionRead &read, const NtfsInspectionRequest &request) {
    validate_ntfs_inspection_request(request);
    const bool directory = request.kind == NtfsSnapshotKind::Directory;
    if (field(read.file, "schema").text != (directory ? "org.disked.ntfs-directory-file-capture/1"
                                                      : "org.disked.ntfs-file-capture/1") ||
        flag(read.file, "authorizes_effects") || flag(read.file, "product_dispatch_admitted"))
        throw std::invalid_argument("ntfs_result_shape");
    if (directory)
        bind_directory_result(read.file, request);
    const auto &original = field(read.file, "observation");
    auto observation = original;
    observation.put("original_schema", field(original, "schema"))
        .put("schema", V::string(directory ? "org.disked.ntfs-directory-projection/1"
                                           : "org.disked.ntfs-bootstrap-projection/1"));
    const auto &regions = field(original, "regions");
    observation.put("regions", rows(regions, regions, 32768, 128));
    for (const auto key : {"primary", "mirror", "volume_record"})
        project_record(observation.fields.at(key));
    project_closures(observation);
    if (directory)
        project_directory(observation);
    const auto version = request.profile == NtfsFileProfile::Automatic   ? "auto"
                         : request.profile == NtfsFileProfile::Version30 ? "3.0"
                                                                         : "3.1";
    auto result = V::object()
                      .put("schema", V::string(directory ? "org.disked.ntfs-directory-inspection/1"
                                                         : "org.disked.ntfs-inspection/1"))
                      .put("command", V::string("image.inspect"))
                      .put("scope", V::string(directory ? "ordinary-local-file-ntfs-directory"
                                                        : "ordinary-local-file-ntfs"))
                      .put("applicability_scope",
                           V::string(directory ? "single-directory-index-envelope"
                                               : "boot-mft0-mirror0-volume-information"))
                      .put("requested_version", V::string(version))
                      .put("file_sha256", V::string(digest(read.file)))
                      .put("capture_sha256", V::string(digest(field(read.file, "capture"))))
                      .put("observation", std::move(observation))
                      .put("capture", field(read.file, "capture"))
                      .put("context", read.context)
                      .put("worker", read.worker)
                      .put("authorizes_effects", V::boolean_value(false));
    if (directory)
        result.put("requested_directory_reference", number(request.directory_reference));
    return result;
}
Outcome dispatch_ntfs_inspection(const std::string &request, const V &parameters,
                                 const NtfsInspectionPort &port) {
    NtfsInspectionRequest input;
    if (!decode_ntfs_inspection(parameters, input))
        return failure(request, "invalid_parameter", 2);
    if (!port)
        return failure(request, "command_unavailable", 3);
    try {
        const auto read = port(input);
        if (read.status != NtfsInspectionRead::Status::Captured) {
            const auto code = read.diagnostic.empty() ? "ntfs_reader_unresolved" : read.diagnostic;
            const auto exit_code = read.status == NtfsInspectionRead::Status::Unresolved ? 6
                                   : code == "ntfs_file_source_changed"                  ? 4
                                                                                         : 3;
            auto out = failure(request, code, exit_code);
            if (read.platform_code)
                out.response.fields.at("diagnostics")
                    .items.front()
                    .put("platform_code", number(read.platform_code));
            if (read.worker.kind != V::Kind::null)
                out.response.put(
                    "result", V::object()
                                  .put("scope", V::string(input.kind == NtfsSnapshotKind::Directory
                                                              ? "ordinary-local-file-ntfs-directory"
                                                              : "ordinary-local-file-ntfs"))
                                  .put("worker", read.worker));
            json::dump(out.response, output_limits());
            return out;
        }
        const auto &observation = field(read.file, "observation"),
                   &capture = field(read.file, "capture");
        const bool changed =
            !flag(capture, "metadata_equal") || !flag(capture, "binding_checks_ok") ||
            !flag(capture, "replay_equal") || !flag(capture, "profile_selection_equal");
        const bool incomplete = !flag(observation, "complete") ||
                                !flag(observation, "applicable") ||
                                !flag(capture, "observed_stable");
        auto out = completed(request, project_ntfs_inspection(read, input));
        if (changed || incomplete) {
            out.exit_code = 4;
            out.response.put("status", V::string("failed"));
            if (incomplete)
                out.response.fields.at("diagnostics")
                    .items.push_back(diagnostic("ntfs_capture_incomplete"));
            if (changed)
                out.response.fields.at("diagnostics")
                    .items.push_back(diagnostic("ntfs_source_changed"));
        }
        json::dump(out.response, output_limits());
        return out;
    } catch (const json::Error &) {
        return failure(request, "ntfs_report_limit", 4);
    } catch (const std::exception &) {
        return failure(request, "internal_error", 4);
    }
}
} // namespace disked
