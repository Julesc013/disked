#include "ntfs_membership.h"
#include "ntfs_membership_detail.h"
#include <map>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace disked {
void validate_ntfs_membership_request(const NtfsMembershipRequest &r) {
    validate_ntfs_directory_request(r.directory);
    if (!r.targets || r.targets > 256)
        throw std::invalid_argument("ntfs_membership_limits");
}
namespace ntfs_membership_detail {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
using Key = std::tuple<std::uint64_t, unsigned, Bytes>;
struct Stop {
    std::string code;
};
[[noreturn]] void stop(std::string code) {
    throw Stop{std::move(code)};
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
V flag(bool n) {
    return V::boolean_value(n);
}
class Collector {
    struct Target {
        unsigned sequence;
        std::size_t row;
        std::map<Key, std::size_t> counts;
    };
    const std::vector<ntfs_directory_detail::Edge> &edges_;
    const std::size_t limit_;
    const Port port_;
    V &out_;
    std::map<std::uint64_t, Target> targets_;
    std::size_t compared_ = 0, matched_ = 0;

    void sync() {
        out_.put("edge_count", exact(edges_.size()))
            .put("compared_edges", exact(compared_))
            .put("matched_edges", exact(matched_))
            .put("unmatched_edges", exact(compared_ - matched_))
            .put("target_count", exact(targets_.size()));
    }
    void charge(const V &value) {
        auto limits = json::Limits{};
        limits.bytes = limits.string_bytes = 1048576;
        limits.values = 262144;
        port_.charge(json::dump(value, limits).size() + 2);
    }
    Target &target(std::uint64_t reference) {
        const auto ordinal = reference & ((std::uint64_t(1) << 48) - 1);
        const auto sequence = static_cast<unsigned>(reference >> 48);
        auto found = targets_.find(ordinal);
        if (found != targets_.end()) {
            if (found->second.sequence != sequence)
                stop("ntfs_membership_reference_conflict");
            return found->second;
        }
        if (targets_.size() == limit_)
            stop("ntfs_membership_target_budget");
        port_.charge(512); // Row control fields; source callback charges its details.
        const auto at = targets_.size();
        auto inserted = targets_.emplace(ordinal, Target{sequence, at, {}});
        out_.fields.at("targets").items.push_back(
            V::object().put("reference", exact(reference)).put("inventory_complete", flag(false)));
        sync();
        auto &row = out_.fields.at("targets").items.back();
        auto result = port_.target(reference, row);
        if (!result.names) {
            const auto *diagnostic = result.observation.find("diagnostic");
            if (!diagnostic || diagnostic->kind != V::Kind::string || diagnostic->text.empty())
                throw std::logic_error("ntfs_membership_inventory");
            const auto &code = diagnostic->text;
            stop("ntfs_membership_" + (code.compare(0, 5, "ntfs_") ? code : code.substr(5)));
        }
        auto &stored = inserted.first->second;
        for (const auto &name : *result.names)
            ++stored.counts[Key{name.parent_reference, name.namespace_code, name.name}];
        row.put("inventory_complete", flag(true));
        return stored;
    }
    void run() {
        for (const auto &edge : edges_) {
            auto &selected = target(edge.reference);
            const auto found =
                selected.counts.find(Key{edge.parent, edge.namespace_code, edge.name});
            const auto count = found == selected.counts.end() ? 0 : found->second;
            auto row = V::object()
                           .put("header_number", exact(edge.header))
                           .put("reference", exact(edge.reference))
                           .put("target_index", exact(selected.row))
                           .put("matching_instances", exact(count))
                           .put("corresponds", flag(count != 0));
            charge(row);
            out_.fields.at("edges").items.push_back(std::move(row));
            ++compared_;
            if (count)
                ++matched_;
            sync();
        }
        out_.put("collection_complete", flag(true))
            .put("all_edges_matched", flag(matched_ == compared_))
            .put("diagnostic",
                 V::string(matched_ == compared_ ? "" : "ntfs_membership_name_mismatch"));
    }

  public:
    Collector(const std::vector<ntfs_directory_detail::Edge> &edges, std::size_t limit, Port port,
              V &out)
        : edges_(edges), limit_(limit), port_(std::move(port)), out_(out) {
    }
    void collect() {
        out_ = V::object()
                   .put("schema", V::string("org.disked.ntfs-name-correspondence/1"))
                   .put("target_limit", exact(limit_))
                   .put("collection_complete", flag(false))
                   .put("all_edges_matched", flag(false))
                   .put("diagnostic", V::string(""))
                   .put("namespace_verified", flag(false))
                   .put("collation_verified", flag(false))
                   .put("lookup_verified", flag(false))
                   .put("uniqueness_verified", flag(false))
                   .put("targets", V::array())
                   .put("edges", V::array());
        sync();
        port_.charge(2048);
        try {
            run();
        } catch (const Stop &failure) {
            out_.put("diagnostic", V::string(failure.code));
        }
        sync();
    }
};
} // namespace
void collect(const std::vector<ntfs_directory_detail::Edge> &edges, std::size_t targets, Port port,
             V &out) {
    if (!port.target || !port.charge || !targets || targets > 256 || edges.size() > 4096)
        throw std::invalid_argument("ntfs_membership_port");
    std::size_t previous = 0;
    for (const auto &edge : edges) {
        if (!edge.header || edge.header <= previous || edge.header > 4096 ||
            !(edge.reference >> 48) || !(edge.parent >> 48) || edge.namespace_code > 3 ||
            edge.name.empty() || edge.name.size() > 510 || edge.name.size() % 2)
            throw std::invalid_argument("ntfs_membership_edges");
        previous = edge.header;
    }
    Collector(edges, targets, std::move(port), out).collect();
}
} // namespace ntfs_membership_detail
} // namespace disked
