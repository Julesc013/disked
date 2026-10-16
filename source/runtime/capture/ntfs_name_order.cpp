#include "ntfs_name_order.h"
#include "portable/hash/sha256.h"
#include "portable/ntfs/ntfs.h"
#include <algorithm>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace disked {
namespace ntfs_name_order_detail {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
using Node = std::pair<bool, std::uint64_t>; // Root has its own domain, not a reserved VBN.
[[noreturn]] void invalid() {
    throw std::logic_error("ntfs_name_order_inputs");
}
void need(bool value) {
    if (!value)
        invalid();
}
const V &field(const V &value, const char *name) {
    const auto *found = value.find(name);
    need(value.kind == V::Kind::object && found);
    return *found;
}
const std::string &text(const V &value, const char *name) {
    const auto &found = field(value, name);
    need(found.kind == V::Kind::string);
    return found.text;
}
std::uint64_t integer(const V &value, const char *name) {
    const auto &encoded = text(value, name);
    need(json::decimal_u64(encoded));
    return std::stoull(encoded);
}
bool flag(const V &value, const char *name) {
    const auto &found = field(value, name);
    need(found.kind == V::Kind::boolean);
    return found.boolean;
}
V exact(std::uint64_t value) {
    return V::string(std::to_string(value));
}
json::Limits limits() {
    auto result = json::Limits{};
    result.bytes = result.string_bytes = 1048576;
    result.values = 262144;
    return result;
}
Bytes unhex(const std::string &encoded, std::size_t maximum) {
    need(!(encoded.size() & 1) && encoded.size() / 2 <= maximum &&
         encoded.find_first_not_of("0123456789abcdef") == std::string::npos);
    auto digit = [](char c) { return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10); };
    Bytes bytes;
    bytes.reserve(encoded.size() / 2);
    for (std::size_t i = 0; i < encoded.size(); i += 2)
        bytes.push_back(static_cast<unsigned char>(digit(encoded[i]) * 16 + digit(encoded[i + 1])));
    return bytes;
}
std::string digest(const unsigned char *data, std::size_t size) {
    unsigned char result[32];
    const unsigned char empty = 0;
    sha256(size ? data : &empty, size, result);
    std::string encoded = "sha256:";
    const char digits[] = "0123456789abcdef";
    for (const auto byte : result) {
        encoded += digits[byte >> 4];
        encoded += digits[byte & 15];
    }
    return encoded;
}
de_ntfs_name_order compare(const de_ntfs_upcase &table, const Bytes &left, const Bytes &right) {
    const de_view a{left.data(), left.size()}, b{right.data(), right.size()};
    de_ntfs_name_order result{};
    need(de_ntfs_name_compare(&table, &a, &b, &result) == DE_OK);
    return result;
}
struct FoldLess {
    const de_ntfs_upcase *table;
    bool operator()(const Bytes &left, const Bytes &right) const {
        return compare(*table, left, right).upcase_order < 0;
    }
};
struct Key {
    std::uint64_t header, reference;
    unsigned namespace_code;
    Node node;
    Bytes name;
};
struct Task {
    bool is_node;
    Node node;
    std::size_t row;
};
} // namespace

void collect(const NtfsDirectoryRequest &request, const V &directory, const V &upcase,
             const std::function<void(std::size_t)> &charge, V &out) {
    need(charge && out.kind == V::Kind::null &&
         text(directory, "schema") == "org.disked.ntfs-index-collection/1" &&
         flag(directory, "index_complete") &&
         text(upcase, "schema") == "org.disked.ntfs-upcase-table-observation/1" &&
         flag(upcase, "complete") && text(upcase, "source_id") == request.capture.source_id &&
         integer(upcase, "epoch") == request.capture.epoch &&
         integer(upcase, "volume_offset") == request.capture.volume_offset &&
         integer(upcase, "volume_bytes") == request.capture.volume_bytes &&
         integer(upcase, "table_bytes") == DE_NTFS_UPCASE_BYTES);
    const auto reference = integer(directory, "reference");
    need(reference >> 48 && (!request.reference || reference == request.reference));
    const auto bytes = unhex(text(upcase, "table_hex"), DE_NTFS_UPCASE_BYTES);
    need(bytes.size() == DE_NTFS_UPCASE_BYTES &&
         digest(bytes.data(), bytes.size()) == text(upcase, "table_sha256"));
    de_view pages[DE_NTFS_UPCASE_PAGES];
    for (std::size_t i = 0; i < DE_NTFS_UPCASE_PAGES; ++i)
        pages[i] = de_view{bytes.data() + i * DE_NTFS_UPCASE_PAGE_BYTES, DE_NTFS_UPCASE_PAGE_BYTES};
    de_ntfs_upcase table{};
    need(de_ntfs_upcase_init(pages, DE_NTFS_UPCASE_PAGES, request.capture.major,
                             request.capture.minor, &table) == DE_OK);
    const auto &entries = field(directory, "entries");
    const auto count = integer(directory, "name_count");
    need(entries.kind == V::Kind::array && !entries.items.empty() &&
         entries.items.size() <= request.limits.entries && entries.items.size() <= 4096 &&
         entries.items.size() == integer(directory, "header_count") &&
         count <= entries.items.size());
    std::map<Node, std::vector<std::size_t>> nodes;
    for (std::size_t i = 0; i < entries.items.size(); ++i) {
        const auto &row = entries.items[i];
        const auto &vbn = field(row, "index_vbn");
        const Node node{vbn.kind == V::Kind::null,
                        vbn.kind == V::Kind::null ? 0 : integer(row, "index_vbn")};
        need(integer(row, "header_number") == i + 1 && flag(row, "present") &&
             flag(row, "envelope_valid"));
        auto &members = nodes[node];
        need(members.empty() || !flag(entries.items[members.back()], "end_marker"));
        members.push_back(i);
    }
    const Node root{true, 0};
    need(nodes.count(root) && nodes.size() <= request.limits.blocks + 1 && nodes.size() <= 129);
    for (const auto &node : nodes)
        need(flag(entries.items[node.second.back()], "end_marker"));
    const auto encoded_directory = json::dump(directory, limits());
    charge(2048);
    out =
        V::object()
            .put("schema", V::string("org.disked.ntfs-directory-name-order/1"))
            .put("policy", V::string("supplied-table-key-observations/1"))
            .put("case_policy", V::string("unobserved"))
            .put("source_id", V::string(request.capture.source_id))
            .put("epoch", exact(request.capture.epoch))
            .put("volume_offset", exact(request.capture.volume_offset))
            .put("volume_bytes", exact(request.capture.volume_bytes))
            .put("directory_reference", exact(reference))
            .put("table_sha256", field(upcase, "table_sha256"))
            .put("directory_sha256",
                 V::string(digest(reinterpret_cast<const unsigned char *>(encoded_directory.data()),
                                  encoded_directory.size())))
            .put("complete", V::boolean_value(false))
            .put("mapped_nondecreasing", V{})
            .put("key_count", exact(count));
    for (const auto *name :
         {"namespace_verified", "collation_verified", "target_membership_verified",
          "alias_resolution_admitted", "lookup_admitted"})
        out.put(name, V::boolean_value(false));
    for (const auto *name : {"order", "adjacent", "reference_groups", "mapped_groups"})
        out.put(name, V::array());
    for (const auto *name : {"keys_returned", "adjacent_returned", "reference_groups_returned",
                             "mapped_groups_returned"})
        out.put(name, exact(0));
    auto append = [&](const char *array, const char *counter, V row) {
        charge(json::dump(row, limits()).size() + 2);
        auto &stored = out.fields.at(array).items;
        stored.push_back(std::move(row));
        out.put(counter, exact(stored.size()));
    };
    std::vector<Task> pending{{true, root, 0}};
    std::set<Node> visited;
    std::vector<Key> ordered;
    while (!pending.empty()) {
        const auto task = pending.back();
        pending.pop_back();
        if (task.is_node) {
            const auto found = nodes.find(task.node);
            need(found != nodes.end() && visited.insert(task.node).second);
            for (auto i = found->second.rbegin(); i != found->second.rend(); ++i) {
                const auto &row = entries.items[*i];
                if (!flag(row, "end_marker"))
                    pending.push_back(Task{false, task.node, *i});
                if (flag(row, "has_child"))
                    pending.push_back(Task{true, Node{false, integer(row, "child_vbn")}, 0});
                else
                    need(field(row, "child_vbn").kind == V::Kind::null);
                need(pending.size() <= 4225);
            }
            continue;
        }
        const auto &row = entries.items[task.row];
        const auto namespace_code = integer(row, "namespace"), target = integer(row, "reference");
        auto name = unhex(text(row, "name_hex"), 510);
        need(!name.empty() && !(name.size() & 1) && namespace_code <= 3 && target >> 48 &&
             integer(row, "parent_reference") == reference && flag(row, "parent_matches"));
        Key key{integer(row, "header_number"), target, static_cast<unsigned>(namespace_code),
                task.node, std::move(name)};
        append("order", "keys_returned",
               V::object()
                   .put("position", exact(ordered.size()))
                   .put("header_number", exact(key.header))
                   .put("index_vbn", key.node.first ? V{} : exact(key.node.second)));
        ordered.push_back(std::move(key));
    }
    need(visited.size() == nodes.size() && ordered.size() == count);
    bool nondecreasing = true;
    for (std::size_t i = 1; i < ordered.size(); ++i) {
        const auto &a = ordered[i - 1], &b = ordered[i];
        const auto result = compare(table, a.name, b.name);
        append("adjacent", "adjacent_returned",
               V::object()
                   .put("left_header", exact(a.header))
                   .put("right_header", exact(b.header))
                   .put("raw_order", V::string(std::to_string(result.raw_order)))
                   .put("upcase_order", V::string(std::to_string(result.upcase_order))));
        nondecreasing = nondecreasing && result.upcase_order <= 0;
    }
    std::map<std::uint64_t, std::vector<std::size_t>> references;
    std::map<Bytes, std::vector<std::size_t>, FoldLess> mapped{FoldLess{&table}};
    for (std::size_t i = 0; i < ordered.size(); ++i) {
        references[ordered[i].reference].push_back(i);
        mapped[ordered[i].name].push_back(i);
    }
    auto headers = [&](const std::vector<std::size_t> &members) {
        auto values = V::array();
        for (const auto i : members)
            values.items.push_back(exact(ordered[i].header));
        return values;
    };
    for (const auto &group : references) {
        if (group.second.size() < 2)
            continue;
        std::set<unsigned> namespaces;
        for (const auto i : group.second)
            namespaces.insert(ordered[i].namespace_code);
        auto codes = V::array();
        for (const auto code : namespaces)
            codes.items.push_back(exact(code));
        append("reference_groups", "reference_groups_returned",
               V::object()
                   .put("reference", exact(group.first))
                   .put("headers", headers(group.second))
                   .put("namespace_codes", std::move(codes)));
    }
    for (const auto &group : mapped) {
        if (group.second.size() < 2)
            continue;
        std::set<std::uint64_t> targets;
        bool raw_equal = true;
        for (const auto i : group.second) {
            targets.insert(ordered[i].reference);
            raw_equal = raw_equal && ordered[i].name == ordered[group.second.front()].name;
        }
        append("mapped_groups", "mapped_groups_returned",
               V::object()
                   .put("headers", headers(group.second))
                   .put("distinct_references", exact(targets.size()))
                   .put("raw_equal", V::boolean_value(raw_equal)));
    }
    out.put("mapped_nondecreasing", V::boolean_value(nondecreasing))
        .put("complete", V::boolean_value(true));
}
} // namespace ntfs_name_order_detail
} // namespace disked
