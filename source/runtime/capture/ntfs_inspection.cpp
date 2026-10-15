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
    limits.bytes = ntfs_inspection_response_bytes;
    limits.values = 65536;
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
    return view && view->kind == V::Kind::string && view->text == "ntfs";
}
bool decode_ntfs_inspection(const V &parameters, NtfsInspectionRequest &result) {
    try {
        if (parameters.kind != V::Kind::object || !ntfs_inspection_parameters(parameters))
            return false;
        const std::set<std::string> keys = {"path", "view", "volume_offset", "volume_bytes",
                                            "ntfs_version"};
        for (const auto &entry : parameters.fields)
            if (!keys.count(entry.first))
                return false;
        const auto &path = field(parameters, "path");
        if (path.kind != V::Kind::string || path.text.empty() || path.text.size() > 32768 ||
            path.text.find('\0') != path.text.npos || !json::valid_utf8(path.text))
            return false;
        NtfsInspectionRequest selected;
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
        result = std::move(selected);
        return true;
    } catch (const std::exception &) {
        return false;
    }
}
V project_ntfs_inspection(const NtfsInspectionRead &read, const NtfsInspectionRequest &request) {
    if (field(read.file, "schema").text != "org.disked.ntfs-file-capture/1" ||
        flag(read.file, "authorizes_effects") || flag(read.file, "product_dispatch_admitted"))
        throw std::invalid_argument("ntfs_result_shape");
    const auto &original = field(read.file, "observation");
    auto observation = original;
    observation.put("original_schema", field(original, "schema"))
        .put("schema", V::string("org.disked.ntfs-bootstrap-projection/1"));
    const auto &regions = field(original, "regions");
    observation.put("regions", rows(regions, regions, 32768, 128));
    for (const auto key : {"primary", "mirror", "volume_record"})
        project_record(observation.fields.at(key));
    const auto version = request.profile == NtfsFileProfile::Automatic   ? "auto"
                         : request.profile == NtfsFileProfile::Version30 ? "3.0"
                                                                         : "3.1";
    return V::object()
        .put("schema", V::string("org.disked.ntfs-inspection/1"))
        .put("command", V::string("image.inspect"))
        .put("scope", V::string("ordinary-local-file-ntfs"))
        .put("applicability_scope", V::string("boot-mft0-mirror0-volume-information"))
        .put("requested_version", V::string(version))
        .put("file_sha256", V::string(digest(read.file)))
        .put("capture_sha256", V::string(digest(field(read.file, "capture"))))
        .put("observation", std::move(observation))
        .put("capture", field(read.file, "capture"))
        .put("context", read.context)
        .put("worker", read.worker)
        .put("authorizes_effects", V::boolean_value(false));
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
                out.response.put("result", V::object()
                                               .put("scope", V::string("ordinary-local-file-ntfs"))
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
