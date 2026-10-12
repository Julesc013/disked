#include "fat_namespace.h"
#include <algorithm>
#include <map>
#include <set>
#include <stdexcept>

namespace disked {
void withdraw_fat_namespace_applicability(json::Value &names, const char *diagnostic) {
    names.put("capture_applicable", json::Value::boolean_value(false));
    names.fields.at("diagnostics").items.push_back(json::Value::string(diagnostic));
    for (auto &directory : names.fields.at("directories").items)
        directory.put("model_complete", json::Value::boolean_value(false));
    for (auto &query : names.fields.at("queries").items) {
        const auto status = query.fields.at("status").text;
        if (status == "unique" || status == "not_found") {
            query.put("status", json::Value::string("incomplete"));
            query.fields.erase("entry_id");
        }
    }
}
namespace {
using V = json::Value;
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V units(const FatNameUnits &name) {
    auto out = V::array();
    for (auto n : name)
        out.items.push_back(exact(n));
    return out;
}
std::string raw(const std::array<unsigned char, 11> &name) {
    const char digits[] = "0123456789abcdef";
    std::string out;
    for (auto c : name) {
        out += digits[c >> 4];
        out += digits[c & 15];
    }
    return out;
}
json::Limits json_limits() {
    json::Limits l;
    l.bytes = 1048576;
    l.string_bytes = 524288;
    l.values = 262144;
    l.depth = 32;
    return l;
}
bool assessment_valid(const FatNameAssessment &a) {
    return (a.state == FatNameState::Known || a.state == FatNameState::Rejected ||
            a.state == FatNameState::Unknown) &&
           a.reason.size() <= 128 && a.reason.find('\0') == std::string::npos &&
           json::valid_utf8(a.reason);
}
const char *state(FatNameState s) {
    return s == FatNameState::Known      ? "known"
           : s == FatNameState::Rejected ? "rejected"
                                         : "unknown";
}
struct Alias {
    std::size_t entry, parent;
    const char *form;
    FatNameUnits name;
};
} // namespace
void validate_fat_name_consumer(const FatNameConsumer &c) {
    if (c.id.empty() || c.id.size() > 128 || c.id.find('\0') != std::string::npos ||
        !json::valid_utf8(c.id) || !c.decode_short || !c.component || !c.equal ||
        c.binding.kind != V::Kind::object)
        throw std::invalid_argument("fat_name_consumer");
    auto l = json_limits();
    l.bytes = 8192;
    l.values = 1024;
    l.depth = 16;
    json::dump(c.binding, l);
}
void validate_fat_name_queries(const std::vector<FatNameQuery> &queries) {
    if (queries.size() > 16)
        throw std::invalid_argument("fat_name_queries");
    for (const auto &q : queries)
        if (q.directory >= 128 || q.component.empty() || q.component.size() > 255)
            throw std::invalid_argument("fat_name_query_shape");
}
json::Value observe_fat_namespace(const std::vector<FatNamespaceDirectory> &directories,
                                  const std::vector<FatNamespaceEntry> &entries,
                                  const FatNameConsumer &consumer,
                                  const std::vector<FatNameQuery> &queries,
                                  const FatNamespaceLimits &limits, bool applicable) {
    validate_fat_name_consumer(consumer);
    validate_fat_name_queries(queries);
    if (directories.size() > 128 || entries.size() > 128 || !limits.comparisons ||
        limits.comparisons > 65536 || !limits.findings || limits.findings > 128 ||
        limits.output_bytes < 16384 || limits.output_bytes > 524288)
        throw std::invalid_argument("fat_namespace_limits");
    std::map<std::size_t, bool> known;
    std::set<std::size_t> ids;
    for (const auto &d : directories)
        if (d.id >= 128 || !known.emplace(d.id, d.records_complete).second)
            throw std::invalid_argument("fat_namespace_directories");
    for (const auto &e : entries)
        if (e.id >= 128 || !ids.insert(e.id).second || !known.count(e.parent) ||
            e.long_name.size() > 260 ||
            (e.kind != FatNamespaceKind::File && e.kind != FatNamespaceKind::Directory &&
             e.kind != FatNamespaceKind::Excluded && e.kind != FatNamespaceKind::Unknown))
            throw std::invalid_argument("fat_namespace_entries");
    auto observed = V::array(), findings = V::array(), diagnostics = V::array();
    std::vector<Alias> aliases;
    bool provider_valid = true, comparison_budget = false, output_budget = false;
    std::size_t calls = 0, total_findings = 0, omitted = 0,
                used = 4096 + json::dump(consumer.binding, json_limits()).size() +
                       directories.size() * 160;
    if (used > limits.output_bytes)
        throw std::invalid_argument("fat_namespace_output_limit");
    auto publish = [&](V &array, V value) {
        const auto bytes = json::dump(value, json_limits()).size() + 16;
        if (bytes > limits.output_bytes - used) {
            output_budget = true;
            return false;
        }
        used += bytes;
        array.items.push_back(std::move(value));
        return true;
    };
    auto finding = [&](V value) {
        ++total_findings;
        if (findings.items.size() == limits.findings || !publish(findings, std::move(value)))
            ++omitted;
    };
    auto assess = [&](const FatNameUnits &name) {
        FatNameAssessment out;
        try {
            out = consumer.component(name);
        } catch (...) {
            out.reason = "consumer_component_exception";
        }
        if (!assessment_valid(out)) {
            provider_valid = false;
            out = {FatNameState::Unknown, "consumer_component_shape"};
        }
        return out;
    };
    auto equal = [&](const FatNameUnits &a, const FatNameUnits &b) {
        if (calls == limits.comparisons) {
            comparison_budget = true;
            return FatNameEquality::Unknown;
        }
        ++calls;
        FatNameEquality out = FatNameEquality::Unknown;
        try {
            out = consumer.equal(a, b);
        } catch (...) {
        }
        if (out != FatNameEquality::Equal && out != FatNameEquality::Different &&
            out != FatNameEquality::Unknown) {
            provider_valid = false;
            return FatNameEquality::Unknown;
        }
        return out;
    };
    for (const auto &e : entries) {
        auto row = V::object()
                       .put("entry_id", exact(e.id))
                       .put("directory_id", exact(e.parent))
                       .put("source_record_offset", exact(e.source_record_offset))
                       .put("stored_oem", V::string(raw(e.short_name)))
                       .put("original_long_units", units(e.long_name));
        auto forms = V::array();
        if (e.kind == FatNamespaceKind::Unknown)
            known[e.parent] = false;
        if (e.kind == FatNamespaceKind::File || e.kind == FatNamespaceKind::Directory) {
            FatNameDecode decoded;
            try {
                decoded = consumer.decode_short(e.short_name);
            } catch (...) {
                decoded.assessment.reason = "consumer_decode_exception";
            }
            if (!assessment_valid(decoded.assessment) || decoded.units.size() > 12 ||
                (decoded.assessment.state == FatNameState::Known && decoded.units.empty())) {
                provider_valid = false;
                decoded.assessment = {FatNameState::Unknown, "consumer_decode_shape"};
                decoded.units.clear();
            }
            auto short_assessment = decoded.assessment;
            if (short_assessment.state == FatNameState::Known)
                short_assessment = assess(decoded.units);
            forms.items.push_back(V::object()
                                      .put("form", V::string("short"))
                                      .put("state", V::string(state(short_assessment.state)))
                                      .put("reason", V::string(short_assessment.reason))
                                      .put("derived_units", units(decoded.units)));
            if (short_assessment.state == FatNameState::Known)
                aliases.push_back({e.id, e.parent, "short", decoded.units});
            else if (short_assessment.state == FatNameState::Unknown)
                known[e.parent] = false;
            if (e.has_long_name) {
                FatNameAssessment long_assessment{FatNameState::Rejected,
                                                  "long_name_not_associated"};
                if (e.long_associated && e.long_unicode_valid && e.long_canonical &&
                    !e.long_name.empty() && e.long_name.size() <= 255)
                    long_assessment = assess(e.long_name);
                else if (e.long_associated)
                    long_assessment.reason = "long_name_not_eligible";
                forms.items.push_back(V::object()
                                          .put("form", V::string("long"))
                                          .put("state", V::string(state(long_assessment.state)))
                                          .put("reason", V::string(long_assessment.reason)));
                if (long_assessment.state == FatNameState::Known)
                    aliases.push_back({e.id, e.parent, "long", e.long_name});
                else if (long_assessment.state == FatNameState::Unknown)
                    known[e.parent] = false;
            }
        } else
            forms.items.push_back(V::object().put(
                "state", V::string(e.kind == FatNamespaceKind::Excluded ? "excluded" : "unknown")));
        row.put("forms", std::move(forms));
        publish(observed, std::move(row));
    }
    for (std::size_t i = 0; i < entries.size(); ++i)
        for (std::size_t j = i + 1; j < entries.size(); ++j)
            if (entries[i].parent == entries[j].parent &&
                entries[i].kind != FatNamespaceKind::Excluded &&
                entries[j].kind != FatNamespaceKind::Excluded &&
                entries[i].short_name == entries[j].short_name)
                finding(V::object()
                            .put("code", V::string("stored_oem_duplicate"))
                            .put("directory_id", exact(entries[i].parent))
                            .put("first_entry", exact(entries[i].id))
                            .put("second_entry", exact(entries[j].id)));
    for (const auto &a : aliases) {
        const auto result = equal(a.name, a.name);
        if (result == FatNameEquality::Different)
            provider_valid = false;
        if (result != FatNameEquality::Equal)
            known[a.parent] = false;
    }
    for (std::size_t i = 0; i < aliases.size(); ++i)
        for (std::size_t j = i + 1; j < aliases.size(); ++j) {
            const auto &a = aliases[i];
            const auto &b = aliases[j];
            if (a.parent != b.parent)
                continue;
            const auto forward = equal(a.name, b.name), reverse = equal(b.name, a.name);
            if (forward != reverse) {
                provider_valid = false;
                known[a.parent] = false;
            }
            if (forward == FatNameEquality::Unknown || reverse == FatNameEquality::Unknown)
                known[a.parent] = false;
            if (forward == FatNameEquality::Equal && reverse == FatNameEquality::Equal &&
                a.entry != b.entry)
                finding(V::object()
                            .put("code", V::string("consumer_alias_collision"))
                            .put("directory_id", exact(a.parent))
                            .put("first_entry", exact(a.entry))
                            .put("second_entry", exact(b.entry))
                            .put("first_form", V::string(a.form))
                            .put("second_form", V::string(b.form)));
        }
    auto results = V::array();
    for (const auto &q : queries) {
        auto row = V::object()
                       .put("directory_id", exact(q.directory))
                       .put("query_units", units(q.component));
        auto matches = V::array();
        std::set<std::size_t> match_ids;
        auto eligibility = assess(q.component);
        bool complete = known.count(q.directory) && known[q.directory];
        if (!known.count(q.directory))
            row.put("status", V::string("directory_not_observed"));
        else if (eligibility.state == FatNameState::Rejected)
            row.put("status", V::string("query_rejected"));
        else if (eligibility.state == FatNameState::Unknown) {
            complete = false;
            row.put("status", V::string("incomplete"));
        } else {
            for (const auto &a : aliases) {
                if (a.parent != q.directory)
                    continue;
                const auto forward = equal(q.component, a.name),
                           reverse = equal(a.name, q.component);
                if (forward != reverse)
                    provider_valid = false;
                if (forward == FatNameEquality::Unknown || reverse == FatNameEquality::Unknown)
                    complete = false;
                if (forward == FatNameEquality::Equal && reverse == FatNameEquality::Equal)
                    match_ids.insert(a.entry);
            }
            for (auto id : match_ids)
                matches.items.push_back(exact(id));
            const char *status = match_ids.size() > 1 ? "ambiguous"
                                                      : (!complete || !applicable ? "incomplete"
                                                         : match_ids.empty()      ? "not_found"
                                                                                  : "unique");
            row.put("status", V::string(status));
            if (std::string(status) == "unique")
                row.put("entry_id", exact(*match_ids.begin()));
        }
        row.put("query_eligibility", V::string(state(eligibility.state)))
            .put("reason", V::string(eligibility.reason))
            .put("matches", std::move(matches))
            .put("directory_complete", V::boolean_value(complete));
        publish(results, std::move(row));
    }
    if (!provider_valid)
        diagnostics.items.push_back(V::string("consumer_comparison_invalid"));
    if (comparison_budget)
        diagnostics.items.push_back(V::string("namespace_comparison_budget"));
    if (output_budget)
        diagnostics.items.push_back(V::string("namespace_output_budget"));
    if (!applicable)
        diagnostics.items.push_back(V::string("capture_not_applicable"));
    if (!provider_valid || comparison_budget || output_budget)
        for (auto &r : results.items)
            if (r.find("status")->text != "query_rejected" &&
                r.find("status")->text != "directory_not_observed") {
                r.put("status", V::string("incomplete"));
                r.fields.erase("entry_id");
                r.put("directory_complete", V::boolean_value(false));
            }
    auto directory_results = V::array();
    for (const auto &d : directories)
        directory_results.items.push_back(
            V::object()
                .put("id", exact(d.id))
                .put("records_complete", V::boolean_value(d.records_complete))
                .put("model_complete",
                     V::boolean_value(known[d.id] && provider_valid && !comparison_budget &&
                                      !output_budget && applicable)));
    auto out = V::object()
                   .put("schema", V::string("org.disked.fat-namespace-observation/1"))
                   .put("consumer_id", V::string(consumer.id))
                   .put("consumer_binding", consumer.binding)
                   .put("capture_applicable", V::boolean_value(applicable))
                   .put("provider_valid", V::boolean_value(provider_valid))
                   .put("directories", std::move(directory_results))
                   .put("entries", std::move(observed))
                   .put("aliases", exact(aliases.size()))
                   .put("comparison_calls", exact(calls))
                   .put("findings", std::move(findings))
                   .put("total_findings", exact(total_findings))
                   .put("omitted_findings", exact(omitted))
                   .put("details_complete", V::boolean_value(!output_budget && !omitted))
                   .put("queries", std::move(results))
                   .put("diagnostics", std::move(diagnostics))
                   .put("storage_consumer_qualified", V::boolean_value(false))
                   .put("authorizes_effects", V::boolean_value(false));
    if (json::dump(out, json_limits()).size() > limits.output_bytes)
        throw std::runtime_error("fat_namespace_output_accounting");
    return out;
}
} // namespace disked
