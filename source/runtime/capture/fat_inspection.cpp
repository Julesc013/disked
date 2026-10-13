#include "fat_inspection.h"
#include "fat_content.h"
#include "portable/hash/sha256.h"
#include <set>

namespace disked {
namespace {
using V = json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("fat_result_shape");
    return *p;
}
bool flag(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::boolean)
        throw std::invalid_argument("fat_result_shape");
    return p.boolean;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string || !json::decimal_u64(p.text))
        throw std::invalid_argument("fat_result_integer");
    return std::stoull(p.text);
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
json::Limits full_limits() {
    json::Limits l;
    l.bytes = 8 * 1024 * 1024;
    l.values = 524288;
    l.depth = 40;
    l.string_bytes = 32768;
    return l;
}
json::Limits output_limits() {
    auto l = full_limits();
    l.bytes = fat_inspection_response_bytes;
    l.values = 65536;
    return l;
}
std::string hash(const V &value) {
    const auto bytes = json::dump(value, full_limits());
    unsigned char result[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), result);
    const char digits[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (auto c : result) {
        out += digits[c >> 4];
        out += digits[c & 15];
    }
    return out;
}
std::size_t bytes(const V &value) {
    return json::dump(value, full_limits()).size();
}
V bounded_rows(const V &rows, std::size_t budget, std::size_t count_limit = 128) {
    if (rows.kind != V::Kind::array)
        throw std::invalid_argument("fat_result_shape");
    auto out = V::array();
    std::size_t used = 0;
    for (const auto &row : rows.items) {
        const auto size = bytes(row) + 1;
        if (out.items.size() == count_limit || size > budget - used)
            break;
        out.items.push_back(row);
        used += size;
    }
    const auto returned = out.items.size();
    return V::object()
        .put("items", std::move(out))
        .put("total", number(rows.items.size()))
        .put("sha256", V::string(hash(rows)))
        .put("returned", number(returned));
}
V projection(const V &rows, std::size_t budget, std::size_t count_limit = 128) {
    auto out = bounded_rows(rows, budget, count_limit);
    const auto returned = out.fields.at("items").items.size();
    out.put("returned", number(returned)).put("omitted", number(rows.items.size() - returned));
    return out;
}
} // namespace
bool fat_inspection_parameters(const V &parameters) {
    const auto *view = parameters.find("view");
    return view && view->kind == V::Kind::string && view->text == "fat";
}
bool decode_fat_inspection(const V &params, FatInspectionRequest &output) {
    try {
        if (!fat_inspection_parameters(params))
            return false;
        const std::set<std::string> keys = {"path",
                                            "view",
                                            "volume_offset",
                                            "volume_bytes",
                                            "fat_copy",
                                            "allocation_scan",
                                            "allocation_window",
                                            "auxiliary_checks",
                                            "name_code_page",
                                            "lookup", "retain_capture"};
        if (params.kind != V::Kind::object)
            return false;
        for (const auto &p : params.fields)
            if (!keys.count(p.first))
                return false;
        const auto &path = field(params, "path");
        if (path.kind != V::Kind::string || path.text.empty() || path.text.size() > 32768 ||
            !json::valid_utf8(path.text) || path.text.find('\0') != path.text.npos)
            return false;
        FatInspectionRequest r;
        r.path = path.text;
        r.volume_offset = integer(params, "volume_offset");
        r.volume_bytes = integer(params, "volume_bytes");
        if (!r.volume_bytes || r.volume_offset > UINT64_MAX - r.volume_bytes)
            return false;
        if (params.find("fat_copy")) {
            const auto copy = integer(params, "fat_copy");
            if (copy > 0xffffffffULL)
                return false;
            r.fat_copy = static_cast<std::uint32_t>(copy);
        }
        for (const auto key : {"allocation_scan", "auxiliary_checks", "retain_capture"})
            if (const auto *p = params.find(key)) {
                if (p->kind != V::Kind::string || (p->text != "yes" && p->text != "no"))
                    return false;
                if (std::string(key) == "allocation_scan") r.allocation_scan = p->text == "yes";
                else if (std::string(key) == "auxiliary_checks") r.auxiliary_checks = p->text == "yes";
                else r.retain_capture = p->text == "yes";
            }
        if (params.find("name_code_page")) {
            const auto page = integer(params, "name_code_page");
            if (page != 437 && page != 850 && page != 932)
                return false;
            r.name_code_page = static_cast<std::uint32_t>(page);
        }
        if (const auto *window = params.find("allocation_window")) {
            if (r.allocation_scan || window->kind != V::Kind::object || window->fields.size() != 2)
                return false;
            const auto first = integer(*window, "first_cluster"),
                       count = integer(*window, "clusters");
            if (first < 2 || first > 268435446 || !count || count > 8192)
                return false;
            r.allocation_window = {static_cast<std::uint32_t>(first),
                                   static_cast<std::uint32_t>(count)};
        }
        if (const auto *lookup = params.find("lookup")) {
            if (!r.name_code_page || lookup->kind != V::Kind::object || lookup->fields.size() != 2)
                return false;
            const auto directory = integer(*lookup, "directory");
            if (directory >= 128)
                return false;
            const auto &names = field(*lookup, "names");
            if (names.kind != V::Kind::array || names.items.empty() || names.items.size() > 16 ||
                bytes(*lookup) > 16384)
                return false;
            for (const auto &name : names.items) {
                if (name.kind != V::Kind::string || name.text.empty() ||
                    name.text.find('\0') != name.text.npos)
                    return false;
                const auto units = json::utf16_units(name.text);
                if (units.empty() || units.size() > 255)
                    return false;
                r.queries.push_back({static_cast<std::size_t>(directory), units});
            }
        }
        output = std::move(r);
        return true;
    } catch (const std::exception &) {
        return false;
    }
}
V project_fat_inspection(const FatInspectionRead &read, bool basic_selection) {
    const auto &original = field(read.file, "observation");
    auto observation = original;
    const auto selection_digest = basic_selection ? fat_content_metadata_digest(original) : std::string();
    auto rows = V::array();
    for (const auto &original_row : field(original, "nodes").items) {
        auto row = original_row;
        auto details = V::object();
        for (const auto key : {"cells", "extents", "orphan_records"})
            if (const auto *p = row.find(key)) {
                details.put(key, V::object()
                                     .put("count", number(p->items.size()))
                                     .put("sha256", V::string(hash(*p))));
                row.fields.erase(key);
            }
        if (basic_selection && field(original_row, "kind").text == "file") {
            row.put("extraction_selector", V::object()
                .put("kind", V::string("fat-file"))
                .put("volume_offset", field(original, "volume_offset"))
                .put("volume_bytes", field(original, "volume_bytes"))
                .put("fat_copy", field(original, "fat_copy"))
                .put("node_id", field(original_row, "id"))
                .put("expected_file_bytes", field(original_row, "file_bytes"))
                .put("metadata_digest", V::string(selection_digest)));
        }
        row.put("detail_bindings", std::move(details));
        rows.items.push_back(std::move(row));
    }
    auto nodes = projection(rows, 262144);
    observation.put("nodes", std::move(nodes));
    if (const auto *links = original.find("cross_links"))
        observation.put("cross_links", projection(*links, 16384, 4096));
    if (const auto *scan = original.find("allocation_scan")) {
        auto selected = *scan;
        if (const auto *findings = scan->find("findings"))
            selected.put("findings", projection(*findings, 16384));
        observation.put("allocation_scan", std::move(selected));
    }
    if (const auto *aux = original.find("auxiliary_checks")) {
        auto selected = *aux;
        if (const auto *backup = aux->find("backup"))
            if (const auto *records = backup->find("records"))
                selected.fields.at("backup").put("records", projection(*records, 8192, 3));
        observation.put("auxiliary_checks", std::move(selected));
    }
    if (const auto *window = original.find("allocation_window")) {
        auto selected = *window;
        if (const auto *findings = window->find("findings"))
            selected.put("findings", projection(*findings, 16384));
        observation.put("allocation_window", std::move(selected));
    }
    if (const auto *ns = original.find("namespace")) {
        auto names = *ns;
        if (const auto *entries = ns->find("entries"))
            names.put("entries", projection(*entries, 65536));
        if (const auto *findings = ns->find("findings"))
            names.put("findings", projection(*findings, 65536));
        observation.put("namespace", std::move(names));
    }
    auto capture = field(read.file, "capture");
    capture.put("regions", projection(field(capture, "regions"), 16384, 8));
    auto out = V::object()
                   .put("schema", V::string("org.disked.fat-image-observation/1"))
                   .put("command", V::string("image.inspect"))
                   .put("provider", V::string("provider.image.fat.prototype/1"))
                   .put("scope", V::string("ordinary-local-file-fat"))
                   .put("observation", std::move(observation))
                   .put("observation_sha256", V::string(hash(original)))
                   .put("capture", std::move(capture))
                   .put("capture_sha256", V::string(hash(field(read.file, "capture"))))
                   .put("context", read.context)
                   .put("worker", read.worker)
                   .put("authorizes_effects", V::boolean_value(false))
                   .put("storage_consumer_qualified", V::boolean_value(false));
    json::dump(out, output_limits());
    return out;
}
Outcome dispatch_fat_inspection(const std::string &request, const V &parameters,
                                const FatInspectionPort &port, FatCaptureStore *store) {
    FatInspectionRequest input;
    if (!decode_fat_inspection(parameters, input))
        return refused(request, "invalid_parameter", 2);
    if (!port)
        return refused(request, "command_unavailable", 3);
    struct Reservation {
        FatCaptureStore *store;
        std::string id;
        ~Reservation() {if (store && !id.empty()) store->abandon(id);}
    } reservation{store, {}};
    try {
        if (input.retain_capture) {
            if (!store) return refused(request, "command_unavailable", 3);
            reservation.id = store->reserve(request);
        }
        const auto read = port(input);
        if (read.status != FatInspectionRead::Status::Captured) {
            const auto code = read.diagnostic.empty() ? "fat_reader_unresolved" : read.diagnostic;
            auto out =
                refused(request, code, read.status == FatInspectionRead::Status::Refused ? 3 : 6);
            if (read.status == FatInspectionRead::Status::Unresolved)
                out.response.put("status", V::string("unknown"));
            if (read.platform_code)
                out.response.fields["diagnostics"].items.front().put("platform_code",
                                                                     number(read.platform_code));
            if (read.worker.kind != V::Kind::null)
                out.response.put("result", V::object()
                                               .put("scope", V::string("ordinary-local-file-fat"))
                                               .put("worker", read.worker));
            return out;
        }
        const auto &obs = field(read.file, "observation"), &capture = field(read.file, "capture");
        bool incomplete = !flag(obs, "selected_tree_complete");
        bool reread_changed = false;
        for (const auto &r : field(capture, "regions").items) {
            incomplete = incomplete || integer(r, "error") || integer(r, "reread_error") ||
                         integer(r, "captured_bytes") != integer(r, "requested_bytes") ||
                         integer(r, "reread_bytes") != integer(r, "requested_bytes");
            if (!integer(r, "error") && !integer(r, "reread_error") &&
                integer(r, "captured_bytes") == integer(r, "requested_bytes") &&
                integer(r, "reread_bytes") == integer(r, "requested_bytes"))
                reread_changed =
                    reread_changed || field(r, "sha256").text != field(r, "reread_sha256").text;
        }
        if (const auto *scan = obs.find("allocation_scan"))
            incomplete = incomplete || !flag(*scan, "coverage_complete") ||
                         !flag(*scan, "comparison_complete");
        if (const auto *window = obs.find("allocation_window"))
            incomplete = incomplete || !flag(*window, "coverage_complete") ||
                         !flag(*window, "comparison_complete");
        if (const auto *aux = obs.find("auxiliary_checks"))
            incomplete = incomplete || !flag(*aux, "coverage_complete");
        if (const auto *ns = obs.find("namespace"))
            for (const auto &directory : field(*ns, "directories").items)
                incomplete = incomplete || !flag(directory, "model_complete");
        const bool changed =
            !flag(capture, "metadata_equal") || !flag(capture, "overlaps_equal") || reread_changed;
        const bool basic = !changed && !input.allocation_scan && !input.auxiliary_checks &&
            !input.allocation_window.clusters && !input.name_code_page && input.queries.empty();
        auto out = completed(request, project_fat_inspection(read, basic));
        if (incomplete || changed) {
            out.exit_code = 4;
            out.response.put("status", V::string("failed"));
            if (incomplete)
                out.response.fields["diagnostics"].items.push_back(
                    diagnostic("fat_capture_incomplete"));
            if (changed)
                out.response.fields["diagnostics"].items.push_back(
                    diagnostic("fat_source_changed"));
        }
        if (input.retain_capture) {
            // The concrete port supplies the already independently verified frame.
            // Check its retained-result/context binding; these hashes alone grant no
            // process authenticity or current-source authority to external records.
            if (field(read.frame, "schema").text != "org.disked.fat-region-frame/1" ||
                hash(field(read.frame, "result")) != hash(read.file) ||
                hash(read.frame) != field(read.context, "frame_sha256").text)
                throw std::invalid_argument("fat_retention_binding");
            auto &result = out.response.fields.at("result");
            result.put("capture_retention", V::object()
                .put("capture_id", V::string(reservation.id))
                .put("bytes", number(FatCaptureStore::record_bytes))
                .put("sha256", V::string("sha256:" + std::string(64, '0')))
                .put("lifetime", V::string("current-process")));
            // Preflight the largest receipt before committing immutable bytes.
            json::dump(out.response, output_limits());
            auto record = V::object().put("schema", V::string("org.disked.retained-fat-capture/1"))
                .put("frame", read.frame).put("context", read.context).put("worker", read.worker);
            result.fields.at("capture_retention") = store->commit(reservation.id, record);
        } else json::dump(out.response, output_limits());
        return out;
    } catch (const FatRetentionError &error) {
        return refused(request, error.what(), std::string(error.what()) == "invalid_parameter" ? 2 : 3);
    } catch (const json::Error &) {
        return refused(request, "fat_report_limit", 3);
    } catch (const std::exception &) {
        return refused(request, "internal_error", 4);
    }
}
} // namespace disked
