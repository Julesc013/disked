#pragma once
#include "runtime/command/json.h"
#include <cstdint>
#include <memory>
#include <vector>

namespace disked {
class CaptureEpochDomain;
// Private profiles. Observation identifiers name evidence, never physical media.
enum class GraphProfile {Fake,Observations};
enum class GraphNodeScope {Fake,Observation};
struct GraphObservation {
    std::string source,context_digest,frame_digest;
    std::uint64_t capture=0,worker=0;
    json::Value payload;
    // Retained only by native owned projections; JSON is not this token.
    std::shared_ptr<const CaptureEpochDomain> domain;
};
struct GraphNode {
    std::string id,kind,identity,media_generation,label,state,capacity_bytes;
    std::vector<std::string> aliases;
    GraphNodeScope scope=GraphNodeScope::Fake;
    GraphObservation observation;
};
struct GraphEdge {std::string from,to,kind;};
struct GraphInput {
    std::vector<GraphNode> nodes;
    std::vector<GraphEdge> edges;
    std::vector<std::string> omissions;
    GraphProfile profile=GraphProfile::Fake;
};
json::Limits graph_limits(GraphProfile profile);
json::Value observation_binding(const GraphNode& node);
std::string observation_node_id(const GraphNode& node);
class GraphSnapshot final {
public:
    static std::shared_ptr<const GraphSnapshot> create(const GraphInput& input,std::uint64_t epoch);
    static std::shared_ptr<const GraphSnapshot> create_owned(std::shared_ptr<const GraphInput> input,std::uint64_t epoch);
    std::shared_ptr<const GraphInput> observation_owner()const{return owner_;}
    const json::Value& value() const {return value_;}
    const std::string& revision() const {return revision_;}
    const json::Value* node(const std::string& id) const;
private:
    static std::shared_ptr<const GraphSnapshot> prepare(const GraphInput&,std::uint64_t,std::shared_ptr<const GraphInput>);
    GraphSnapshot(json::Value value,std::string revision,std::shared_ptr<const GraphInput> owner):
        value_(std::move(value)),revision_(std::move(revision)),owner_(std::move(owner)){}
    const json::Value value_;
    const std::string revision_;
    const std::shared_ptr<const GraphInput> owner_;
};
std::string digest_sha256(const std::string& bytes);
}
