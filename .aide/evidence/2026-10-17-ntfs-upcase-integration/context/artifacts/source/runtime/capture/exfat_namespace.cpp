#include "exfat_namespace.h"
#include "portable/exfat/exfat.h"
#include <algorithm>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>

namespace disked {
namespace {
using V = json::Value;
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
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
V units(const std::vector<unsigned short> &name) {
    auto out = V::array();
    for (auto n : name)
        out.items.push_back(exact(n));
    return out;
}
std::uint64_t native(const de_u64 &n) {
    char text[21];
    if (de_u64_format(&n, text, sizeof(text)))
        throw std::runtime_error("exfat_namespace_internal");
    return std::stoull(text);
}
bool valid_name(const std::vector<unsigned short> &name) {
    if (name.empty() || name.size() > 255 || name == std::vector<unsigned short>{46} ||
        name == std::vector<unsigned short>{46, 46})
        return false;
    for (std::size_t i = 0; i < name.size(); ++i) {
        const auto n = name[i];
        if (n < 32 || n == 34 || n == 42 || n == 47 || n == 58 || n == 60 || n == 62 || n == 63 ||
            n == 92 || n == 124)
            return false;
        if (n >= 0xd800 && n <= 0xdbff) {
            if (++i >= name.size() || name[i] < 0xdc00 || name[i] > 0xdfff)
                return false;
        } else if (n >= 0xdc00 && n <= 0xdfff)
            return false;
    }
    return true;
}
struct Entry {
    std::size_t id, directory;
    std::vector<unsigned short> name;
    unsigned short hash = 0;
    bool usable = false;
};
struct Directory {
    bool records_complete = false, known = true;
};
json::Limits output_limits(std::size_t bytes) {
    json::Limits l;
    l.bytes = bytes;
    l.string_bytes = bytes;
    l.values = 262144;
    l.depth = 32;
    return l;
}
void validate(const std::vector<ExfatNamespaceDirectory> &dirs,
              const std::vector<ExfatNameQuery> &queries, std::uint32_t clusters, unsigned shift,
              const ExfatNamespaceLimits &l) {
    if (!clusters || clusters > DE_EXFAT_MAX_CLUSTERS || shift < 9 || shift > 25 ||
        dirs.size() > 256 || queries.size() > 256 || !l.directories || l.directories > 256 ||
        !l.records || l.records > 4096 || !l.queries || l.queries > 256 || !l.comparisons ||
        l.comparisons > 65536 || !l.findings || l.findings > 128 || l.output_bytes < 16384 ||
        l.output_bytes > 1048576)
        throw std::invalid_argument("exfat_namespace_inputs");
    std::set<std::size_t> ids;
    std::vector<std::uint64_t> offsets;
    for (const auto &dir : dirs) {
        if (!ids.insert(dir.id).second || dir.records.size() > 4096 - offsets.size())
            throw std::invalid_argument("exfat_namespace_inputs");
        for (const auto &record : dir.records) {
            if (record.source_offset > std::numeric_limits<std::uint64_t>::max() - 32)
                throw std::invalid_argument("exfat_namespace_record_bounds");
            offsets.push_back(record.source_offset);
        }
    }
    std::sort(offsets.begin(), offsets.end());
    for (std::size_t i = 1; i < offsets.size(); ++i)
        if (offsets[i] - offsets[i - 1] < 32)
            throw std::invalid_argument("exfat_namespace_record_overlap");
    for (const auto &query : queries)
        if (query.units.empty() || query.units.size() > 255)
            throw std::invalid_argument("exfat_namespace_query");
}
} // namespace

V observe_exfat_namespace(const std::vector<ExfatNamespaceDirectory> &directories,
                          const ExfatUpcaseMap &map, const std::vector<ExfatNameQuery> &queries,
                          std::uint32_t clusters, unsigned shift,
                          const ExfatNamespaceLimits &limits, bool capture_applicable) {
    validate(directories, queries, clusters, shift, limits);
    auto rows = V::array(), entry_rows = V::array(), findings = V::array(),
         diagnostics = V::array();
    std::map<std::size_t, Directory> state;
    std::vector<Entry> entries;
    std::size_t used = 8192, records = 0, comparisons = 0, finding_total = 0;
    bool exhausted = false;
    const auto diagnostic = [&](const char *code) {
        for (const auto &v : diagnostics.items)
            if (v.text == code)
                return;
        diagnostics.items.push_back(V::string(code));
    };
    const auto reserve = [&](std::size_t n) {
        if (n > limits.output_bytes - used) {
            exhausted = true;
            diagnostic("exfat_namespace_output_budget");
            return false;
        }
        used += n;
        return true;
    };
    const auto finding = [&](const char *code, std::size_t dir, std::size_t first,
                             std::size_t second) {
        ++finding_total;
        if (findings.items.size() < limits.findings && reserve(256))
            findings.items.push_back(V::object()
                                         .put("code", V::string(code))
                                         .put("directory_id", exact(dir))
                                         .put("first_entry", exact(first))
                                         .put("second_entry", exact(second)));
    };
    if (!map.valid())
        diagnostic(map.diagnostic().empty() ? "exfat_upcase_mapping" : map.diagnostic().c_str());
    if (!capture_applicable)
        diagnostic("exfat_namespace_capture_inapplicable");
    for (std::size_t di = 0; di < directories.size(); ++di) {
        if (di == limits.directories || !reserve(512)) {
            exhausted = true;
            diagnostic("exfat_namespace_directory_budget");
            break;
        }
        const auto &dir = directories[di];
        Directory ds;
        auto raw = V::array();
        std::size_t covered = 0;
        bool ended = false;
        while (covered < dir.records.size()) {
            if (records == limits.records || !reserve(192)) {
                exhausted = true;
                diagnostic("exfat_namespace_record_budget");
                break;
            }
            const auto at = covered;
            const auto &record = dir.records[at];
            de_view view{record.bytes.data(), 32};
            de_exfat_slot slot{};
            if (de_exfat_slot_read(&view, &slot))
                throw std::runtime_error("exfat_namespace_internal");
            std::size_t count = 1;
            if (!ended && slot.kind == DE_EXFAT_DIR_FILE) {
                count = std::min<std::size_t>(static_cast<std::size_t>(slot.secondary_count) + 1,
                                              dir.records.size() - at);
                if (count > limits.records - records ||
                    !reserve((count - 1) * 192 + count * 64 + 4992)) {
                    exhausted = true;
                    diagnostic("exfat_namespace_record_budget");
                    break;
                }
                std::vector<unsigned char> bytes;
                bytes.reserve(count * 32);
                for (std::size_t n = 0; n < count; ++n)
                    bytes.insert(bytes.end(), dir.records[at + n].bytes.begin(),
                                 dir.records[at + n].bytes.end());
                de_view set{bytes.data(), bytes.size()};
                de_exfat_file_set parsed{};
                if (de_exfat_file_set_read(&set, clusters, shift, 8192, &parsed))
                    throw std::runtime_error("exfat_namespace_internal");
                Entry entry{entries.size() + 1, dir.id, {}, 0, false};
                entry.name.assign(parsed.units, parsed.units + parsed.name_units_present);
                bool hash_known = false, hash_equal = false;
                if (map.valid() && parsed.associated && parsed.encoding_valid &&
                    parsed.name_characters_valid) {
                    if (de_exfat_name_hash(map.mapping().data(), map.mapping().size(),
                                           entry.name.data(), entry.name.size(), &entry.hash))
                        throw std::runtime_error("exfat_namespace_internal");
                    hash_known = true;
                    hash_equal = entry.hash == parsed.name_hash;
                    entry.usable = hash_equal;
                }
                if (!entry.usable) {
                    ds.known = false;
                    finding("exfat_name_inapplicable", dir.id, entry.id, 0);
                }
                if (hash_known && !hash_equal)
                    finding("exfat_name_hash_mismatch", dir.id, entry.id, 0);
                entry_rows.items.push_back(
                    V::object()
                        .put("id", exact(entry.id))
                        .put("directory_id", exact(dir.id))
                        .put("source_record_offset", exact(record.source_offset))
                        .put("raw_set_hex", V::string(hex(bytes.data(), bytes.size())))
                        .put("original_units", units(entry.name))
                        .put("name_length", exact(parsed.name_length))
                        .put("name_usable", V::boolean_value(entry.usable))
                        .put("associated", V::boolean_value(parsed.associated != 0))
                        .put("encoding_valid", V::boolean_value(parsed.encoding_valid != 0))
                        .put("characters_valid",
                             V::boolean_value(parsed.name_characters_valid != 0))
                        .put("issues", exact(parsed.issues))
                        .put("stored_name_hash", exact(parsed.name_hash))
                        .put("calculated_name_hash", hash_known ? exact(entry.hash) : V{})
                        .put("name_hash_matches", hash_known ? V::boolean_value(hash_equal) : V{})
                        .put("kind", V::string(parsed.attributes & 16 ? "directory" : "file"))
                        .put("stream_valid", V::boolean_value(parsed.stream_valid != 0))
                        .put("metadata_valid", V::boolean_value(parsed.metadata_valid != 0))
                        .put("first_cluster", exact(parsed.first_cluster))
                        .put("stream_flags", exact(parsed.stream_flags))
                        .put("data_length", exact(native(parsed.data_length)))
                        .put("valid_data_length", exact(native(parsed.valid_data_length))));
                entries.push_back(std::move(entry));
            } else if (!ended) {
                if (slot.kind == DE_EXFAT_DIR_END)
                    ended = true;
                else if (slot.kind != DE_EXFAT_DIR_UNUSED &&
                         !(dir.root &&
                           (slot.kind == DE_EXFAT_DIR_BITMAP || slot.kind == DE_EXFAT_DIR_UPCASE ||
                            slot.kind == DE_EXFAT_DIR_LABEL)) &&
                         !(slot.benign && slot.kind == DE_EXFAT_DIR_UNKNOWN_PRIMARY)) {
                    ds.known = false;
                    finding("exfat_directory_unsupported_record", dir.id, 0, 0);
                }
            }
            for (std::size_t n = 0; n < count; ++n) {
                const auto &original = dir.records[at + n];
                raw.items.push_back(V::object()
                                        .put("index", exact(at + n))
                                        .put("source_offset", exact(original.source_offset))
                                        .put("raw_hex", V::string(hex(original.bytes.data(), 32))));
            }
            records += count;
            covered += count;
        }
        ds.records_complete = ended || (covered == dir.records.size() && dir.extent_complete);
        if (covered != dir.records.size())
            ds.known = false;
        state.emplace(dir.id, ds);
        rows.items.push_back(
            V::object()
                .put("id", exact(dir.id))
                .put("root", V::boolean_value(dir.root))
                .put("supplied_extent_complete", V::boolean_value(dir.extent_complete))
                .put("records_complete", V::boolean_value(ds.records_complete))
                .put("end_marker", V::boolean_value(ended))
                .put("records_total", exact(dir.records.size()))
                .put("records_covered", exact(covered))
                .put("records", std::move(raw)));
    }
    const auto equal = [&](const std::vector<unsigned short> &a,
                           const std::vector<unsigned short> &b, bool &complete) {
        if (comparisons == limits.comparisons) {
            complete = false;
            exhausted = true;
            diagnostic("exfat_namespace_comparison_budget");
            return false;
        }
        ++comparisons;
        int same = 0;
        if (de_exfat_name_equal(map.mapping().data(), map.mapping().size(), a.data(), a.size(),
                                b.data(), b.size(), &same))
            throw std::runtime_error("exfat_namespace_internal");
        return same != 0;
    };
    if (map.valid()) {
        for (std::size_t i = 0; i < entries.size(); ++i) {
            for (std::size_t j = i + 1; j < entries.size(); ++j) {
                const auto &a = entries[i];
                const auto &b = entries[j];
                if (!a.usable || !b.usable || a.directory != b.directory || a.hash != b.hash)
                    continue;
                bool complete = true;
                if (equal(a.name, b.name, complete))
                    finding("exfat_name_collision", a.directory, a.id, b.id);
                if (!complete)
                    state[a.directory].known = false;
            }
        }
    }
    auto results = V::array();
    std::size_t queries_covered = 0;
    for (const auto &query : queries) {
        if (queries_covered == limits.queries || !reserve(256 + query.units.size() * 16)) {
            exhausted = true;
            diagnostic("exfat_namespace_query_budget");
            break;
        }
        ++queries_covered;
        const auto directory = state.find(query.directory);
        bool complete = directory != state.end() && directory->second.known &&
                        directory->second.records_complete && capture_applicable && map.valid() &&
                        !exhausted;
        auto row = V::object()
                       .put("directory_id", exact(query.directory))
                       .put("original_units", units(query.units));
        auto matches = V::array();
        unsigned short hash = 0;
        const bool eligible = valid_name(query.units);
        if (map.valid() && eligible) {
            if (de_exfat_name_hash(map.mapping().data(), map.mapping().size(), query.units.data(),
                                   query.units.size(), &hash))
                throw std::runtime_error("exfat_namespace_internal");
            for (const auto &entry : entries) {
                if (entry.directory != query.directory || !entry.usable || entry.hash != hash)
                    continue;
                if (equal(query.units, entry.name, complete)) {
                    if (!reserve(24)) {
                        complete = false;
                        break;
                    }
                    matches.items.push_back(exact(entry.id));
                }
            }
        }
        const char *status = directory == state.end()   ? "directory_not_observed"
                             : !eligible                ? "query_rejected"
                             : matches.items.size() > 1 ? "ambiguous"
                             : !complete                ? "incomplete"
                             : matches.items.empty()    ? "not_found"
                                                        : "unique";
        row.put("status", V::string(status))
            .put("comparison_complete", V::boolean_value(complete))
            .put("observed_matches", matches);
        if (std::string(status) == "unique")
            row.put("entry_id", matches.items.front());
        results.items.push_back(std::move(row));
    }
    for (auto &row : rows.items) {
        const auto &dir = state.at(static_cast<std::size_t>(std::stoull(row.fields.at("id").text)));
        row.put("model_complete",
                V::boolean_value(dir.known && dir.records_complete && map.valid() &&
                                 capture_applicable && !exhausted));
    }
    // Measure before moving: C++14 leaves nested receiver/argument order unspecified.
    const auto findings_omitted = finding_total - findings.items.size();
    const auto directories_covered = rows.items.size();
    auto out =
        V::object()
            .put("schema", V::string("org.disked.exfat-namespace/1"))
            .put("scope", V::string("supplied-directory-records"))
            .put("capture_applicable", V::boolean_value(capture_applicable))
            .put("map_valid", V::boolean_value(map.valid()))
            .put("map", map.facts())
            .put("map_diagnostic", map.diagnostic().empty() ? V{} : V::string(map.diagnostic()))
            .put("directories", std::move(rows))
            .put("directories_total", exact(directories.size()))
            .put("directories_covered", exact(directories_covered))
            .put("entries", std::move(entry_rows))
            .put("queries", std::move(results))
            .put("queries_total", exact(queries.size()))
            .put("queries_covered", exact(queries_covered))
            .put("comparisons", exact(comparisons))
            .put("findings_total", exact(finding_total))
            .put("findings_omitted", exact(findings_omitted))
            .put("findings", std::move(findings))
            .put("diagnostics", std::move(diagnostics))
            .put("budget_exhausted", V::boolean_value(exhausted))
            .put("authorizes_effects", V::boolean_value(false))
            .put("physical_admission", V::boolean_value(false));
    try {
        json::dump(out, output_limits(limits.output_bytes));
    } catch (const json::Error &) {
        // Actual encoding remains a final independent bound. No prefix can
        // authorize uniqueness when its complete receipt cannot be emitted.
        return V::object()
            .put("schema", V::string("org.disked.exfat-namespace/1"))
            .put("scope", V::string("supplied-directory-records"))
            .put("diagnostic", V::string("exfat_namespace_output_budget"))
            .put("budget_exhausted", V::boolean_value(true))
            .put("authorizes_effects", V::boolean_value(false))
            .put("physical_admission", V::boolean_value(false));
    }
    return out;
}
} // namespace disked
