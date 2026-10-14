#include "runtime/capture/exfat_namespace.h"
#include <algorithm>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
using V = disked::json::Value;
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("probe_field");
    return *p;
}
std::uint64_t number(const V &v) {
    if (v.kind != V::Kind::string || !disked::json::decimal_u64(v.text))
        throw std::invalid_argument("probe_number");
    return std::stoull(v.text);
}
bool boolean(const V &v) {
    if (v.kind != V::Kind::boolean)
        throw std::invalid_argument("probe_bool");
    return v.boolean;
}
std::vector<unsigned char> bytes(const V &v) {
    if (v.kind != V::Kind::string || v.text.size() % 2 || v.text.size() > 524288)
        throw std::invalid_argument("probe_bytes");
    const auto digit = [](char c) -> unsigned {
        if (c >= '0' && c <= '9')
            return static_cast<unsigned>(c - '0');
        if (c >= 'a' && c <= 'f')
            return static_cast<unsigned>(c - 'a' + 10);
        throw std::invalid_argument("probe_hex");
    };
    std::vector<unsigned char> out;
    for (std::size_t i = 0; i < v.text.size(); i += 2)
        out.push_back(static_cast<unsigned char>(digit(v.text[i]) * 16 + digit(v.text[i + 1])));
    return out;
}
V run(const V &input) {
    const auto table = bytes(field(input, "table"));
    const auto checksum = number(field(input, "checksum"));
    if (checksum > 0xffffffffULL)
        throw std::invalid_argument("probe_checksum");
    const auto format = disked::exfat_upcase_format_from(field(input, "format").text);
    const auto *budget = input.find("map_budget");
    auto map =
        disked::ExfatUpcaseMap::read(table, static_cast<unsigned long>(checksum), format,
                                     budget ? static_cast<std::size_t>(number(*budget)) : 786432);
    const auto &supplied = field(input, "directories");
    if (supplied.kind != V::Kind::array || supplied.items.size() > 256)
        throw std::invalid_argument("probe_directories");
    std::vector<disked::ExfatNamespaceDirectory> directories;
    for (const auto &d : supplied.items) {
        disked::ExfatNamespaceDirectory dir;
        dir.id = static_cast<std::size_t>(number(field(d, "id")));
        dir.root = boolean(field(d, "root"));
        dir.extent_complete = boolean(field(d, "complete"));
        const auto &rs = field(d, "records");
        if (rs.kind != V::Kind::array || rs.items.size() > 4096)
            throw std::invalid_argument("probe_records");
        for (const auto &r : rs.items) {
            auto raw = bytes(field(r, "bytes"));
            if (raw.size() != 32)
                throw std::invalid_argument("probe_record");
            disked::ExfatDirectoryRecord record;
            record.source_offset = number(field(r, "offset"));
            std::copy(raw.begin(), raw.end(), record.bytes.begin());
            dir.records.push_back(record);
        }
        directories.push_back(std::move(dir));
    }
    std::vector<disked::ExfatNameQuery> queries;
    const auto &qs = field(input, "queries");
    if (qs.kind != V::Kind::array || qs.items.size() > 256)
        throw std::invalid_argument("probe_queries");
    for (const auto &q : qs.items) {
        disked::ExfatNameQuery query;
        query.directory = static_cast<std::size_t>(number(field(q, "directory")));
        const auto &name = field(q, "units");
        if (name.kind != V::Kind::array || name.items.size() > 255)
            throw std::invalid_argument("probe_name");
        for (const auto &unit : name.items) {
            const auto n = number(unit);
            if (n > 65535)
                throw std::invalid_argument("probe_unit");
            query.units.push_back(static_cast<unsigned short>(n));
        }
        queries.push_back(std::move(query));
    }
    disked::ExfatNamespaceLimits limits;
    if (const auto *l = input.find("limits")) {
        if (l->kind != V::Kind::object)
            throw std::invalid_argument("probe_limit");
        for (const auto &pair : l->fields) {
            const auto n = static_cast<std::size_t>(number(pair.second));
            if (pair.first == "directories")
                limits.directories = n;
            else if (pair.first == "records")
                limits.records = n;
            else if (pair.first == "queries")
                limits.queries = n;
            else if (pair.first == "comparisons")
                limits.comparisons = n;
            else if (pair.first == "findings")
                limits.findings = n;
            else if (pair.first == "output_bytes")
                limits.output_bytes = n;
            else
                throw std::invalid_argument("probe_limit");
        }
    }
    auto result = disked::observe_exfat_namespace(
        directories, map, queries, 4096, 9, limits,
        input.find("capture_applicable") ? boolean(*input.find("capture_applicable")) : true);
    const char digits[] = "0123456789abcdef";
    std::string original;
    for (auto byte : map.original()) {
        original += digits[byte >> 4];
        original += digits[byte & 15];
    }
    return V::object()
        .put("result", std::move(result))
        .put("map_valid", V::boolean_value(map.valid()))
        .put("map_diagnostic", map.diagnostic().empty() ? V{} : V::string(map.diagnostic()))
        .put("map_original_hex", V::string(original))
        .put("original_retained", V::boolean_value(map.original() == table));
}
} // namespace
int main() {
    disked::json::Limits limits;
    limits.bytes = 4194304;
    limits.string_bytes = 524288;
    limits.values = 262144;
    limits.depth = 32;
    std::string line;
    while (std::getline(std::cin, line)) {
        try {
            std::cout << disked::json::dump(run(disked::json::parse(line, limits)), limits) << "\n";
        } catch (const std::exception &error) {
            std::cout << disked::json::dump(V::object().put("error", V::string(error.what())))
                      << "\n";
        }
    }
}
