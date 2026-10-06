#pragma once
#include "json.h"
#include <cstdint>
#include <memory>
#include <vector>

namespace disked {
// Provider input is copied and validated before publication. These private
// types describe the admitted fake profile, not a general storage ABI.
struct GraphNode {
    std::string id,kind,identity,media_generation,label,state,capacity_bytes;
    std::vector<std::string> aliases;
};
struct GraphEdge {std::string from,to,kind;};
struct GraphInput {
    std::vector<GraphNode> nodes;
    std::vector<GraphEdge> edges;
    std::vector<std::string> omissions;
};
class GraphSnapshot final {
public:
    static std::shared_ptr<const GraphSnapshot> create(const GraphInput& input,std::uint64_t epoch);
    const json::Value& value() const {return value_;}
    const std::string& revision() const {return revision_;}
    const json::Value* node(const std::string& id) const;
private:
    GraphSnapshot(json::Value value,std::string revision):value_(std::move(value)),revision_(std::move(revision)){}
    const json::Value value_;
    const std::string revision_;
};
std::string digest_sha256(const std::string& bytes);
}
