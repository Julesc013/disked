#include "exfat_inspection.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &value, const char *key) {
    const auto *found = value.find(key);
    if (!found)
        throw std::invalid_argument("exfat_result_shape");
    return *found;
}
bool flag(const V &value, const char *key) {
    const auto &found = field(value, key);
    if (found.kind != V::Kind::boolean)
        throw std::invalid_argument("exfat_result_shape");
    return found.boolean;
}
std::uint64_t integer(const V &value, const char *key) {
    const auto &found = field(value, key);
    if (found.kind != V::Kind::string || !json::decimal_u64(found.text))
        throw std::invalid_argument("exfat_result_integer");
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
    limits.bytes = exfat_inspection_response_bytes;
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
V rows(const V &original, std::size_t budget, std::size_t maximum) {
    if (original.kind != V::Kind::array)
        throw std::invalid_argument("exfat_result_shape");
    auto returned = V::array();
    std::size_t used = 0;
    for (const auto &row : original.items) {
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
Outcome failure(const std::string &request, const std::string &code, int exit_code) {
    auto out = refused(request, code, exit_code);
    if (exit_code == 4)
        out.response.put("status", V::string("failed"));
    if (exit_code == 6)
        out.response.put("status", V::string("unknown"));
    return out;
}
} // namespace
bool exfat_inspection_parameters(const V &parameters) {
    const auto *view = parameters.find("view");
    return view && view->kind == V::Kind::string && view->text == "exfat";
}
bool decode_exfat_inspection(const V &parameters, ExfatInspectionRequest &result) {
    try {
        if (parameters.kind != V::Kind::object || !exfat_inspection_parameters(parameters))
            return false;
        const std::set<std::string> keys = {"path", "view", "volume_offset", "volume_bytes",
                                            "upcase_format"};
        for (const auto &entry : parameters.fields)
            if (!keys.count(entry.first))
                return false;
        const auto &path = field(parameters, "path");
        if (path.kind != V::Kind::string || path.text.empty() || path.text.size() > 32768 ||
            path.text.find('\0') != path.text.npos || !json::valid_utf8(path.text))
            return false;
        ExfatInspectionRequest selected;
        selected.path = path.text;
        selected.volume_offset = integer(parameters, "volume_offset");
        selected.volume_bytes = integer(parameters, "volume_bytes");
        const std::uint64_t maximum = 0x7fffffffffffffffULL;
        if (selected.volume_bytes < 512 || selected.volume_offset > maximum ||
            selected.volume_bytes > maximum - selected.volume_offset)
            return false;
        if (const auto *format = parameters.find("upcase_format")) {
            if (format->kind != V::Kind::string)
                return false;
            selected.upcase_format = exfat_upcase_format_from(format->text);
        }
        result = std::move(selected);
        return true;
    } catch (const std::exception &) {
        return false;
    }
}
V project_exfat_inspection(const ExfatInspectionRead &read, const ExfatInspectionRequest &request) {
    if (field(read.file, "schema").text != "org.disked.exfat-file-capture/2" ||
        flag(read.file, "authorizes_effects") || flag(read.file, "product_dispatch_admitted"))
        throw std::invalid_argument("exfat_result_shape");
    const auto &original = field(read.file, "observation");
    auto observation = original;
    observation.put("root_records", rows(field(original, "root_records"), 98304, 256));
    observation.put("regions", rows(field(original, "regions"), 32768, 128));
    for (const auto key : {"root_chain", "bitmap_chain", "upcase_chain"}) {
        auto &chain = observation.fields.at(key);
        chain.put("clusters", rows(field(chain, "clusters"), 4096, 64));
        chain.put("cells", rows(field(chain, "cells"), 16384, 64));
    }
    return V::object()
        .put("schema", V::string("org.disked.exfat-inspection/1"))
        .put("command", V::string("image.inspect"))
        .put("scope", V::string("ordinary-local-file-exfat"))
        .put("applicability_scope", V::string("root-and-active-system-metadata"))
        .put("requested_upcase_format", V::string(exfat_upcase_format_name(request.upcase_format)))
        .put("file_sha256", V::string(digest(read.file)))
        .put("capture_sha256", V::string(digest(field(read.file, "capture"))))
        .put("observation", std::move(observation))
        .put("capture", field(read.file, "capture"))
        .put("context", read.context)
        .put("worker", read.worker)
        .put("authorizes_effects", V::boolean_value(false));
}
Outcome dispatch_exfat_inspection(const std::string &request, const V &parameters,
                                  const ExfatInspectionPort &port) {
    ExfatInspectionRequest input;
    if (!decode_exfat_inspection(parameters, input))
        return failure(request, "invalid_parameter", 2);
    if (!port)
        return failure(request, "command_unavailable", 3);
    try {
        const auto read = port(input);
        if (read.status != ExfatInspectionRead::Status::Captured) {
            const auto code = read.diagnostic.empty() ? "exfat_reader_unresolved" : read.diagnostic;
            const auto exit_code = read.status == ExfatInspectionRead::Status::Unresolved ? 6
                                   : code == "exfat_file_source_changed"                  ? 4
                                                                                          : 3;
            auto out = failure(request, code, exit_code);
            if (read.platform_code)
                out.response.fields.at("diagnostics")
                    .items.front()
                    .put("platform_code", number(read.platform_code));
            if (read.worker.kind != V::Kind::null)
                out.response.put("result", V::object()
                                               .put("scope", V::string("ordinary-local-file-exfat"))
                                               .put("worker", read.worker));
            json::dump(out.response, output_limits());
            return out;
        }
        const auto &observation = field(read.file, "observation"),
                   &capture = field(read.file, "capture");
        const bool changed = !flag(capture, "metadata_equal") ||
                             !flag(capture, "binding_checks_ok") || !flag(capture, "replay_equal");
        const bool incomplete = !flag(observation, "complete") ||
                                !flag(observation, "applicable") ||
                                !flag(capture, "observed_stable");
        auto out = completed(request, project_exfat_inspection(read, input));
        if (changed || incomplete) {
            out.exit_code = 4;
            out.response.put("status", V::string("failed"));
            if (incomplete)
                out.response.fields.at("diagnostics")
                    .items.push_back(diagnostic("exfat_capture_incomplete"));
            if (changed)
                out.response.fields.at("diagnostics")
                    .items.push_back(diagnostic("exfat_source_changed"));
        }
        json::dump(out.response, output_limits());
        return out;
    } catch (const json::Error &) {
        return failure(request, "exfat_report_limit", 4);
    } catch (const std::exception &) {
        return failure(request, "internal_error", 4);
    }
}
} // namespace disked
