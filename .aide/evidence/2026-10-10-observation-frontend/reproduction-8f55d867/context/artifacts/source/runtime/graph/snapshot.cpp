#include "snapshot.h"
#include "sha256.h"
#include <set>

namespace disked {
using json::Value;
namespace {
void require(bool ok,const char* error) {if(!ok)throw std::invalid_argument(error);}
bool bounded(const std::string& s,std::size_t max=256,bool empty=false) {
    return (empty || !s.empty()) && s.size()<=max && json::valid_utf8(s) && s.find('\0')==std::string::npos;
}
bool digest(const std::string& s) {return s.size()==71 && s.compare(0,7,"sha256:")==0 && s.find_first_not_of("0123456789abcdef",7)==std::string::npos;}
bool source_id(const std::string& s) {
    if(s.empty() || s.size()>64)return false;
    for(auto c:s)if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='.' || c=='_' || c=='-' || c=='/'))return false;
    return true;
}
Value strings(const std::vector<std::string>& items) {
    Value v=Value::array();for(const auto& item:items) {require(bounded(item),"invalid_reference");v.items.push_back(Value::string(item));}return v;
}
}
std::string digest_sha256(const std::string& bytes) {
    unsigned char digest[32];sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),digest);
    const char* hex="0123456789abcdef";std::string result="sha256:";
    for(const auto byte:digest) {result+=hex[byte>>4];result+=hex[byte&15];}return result;
}
json::Limits graph_limits(GraphProfile profile) {
    require(profile==GraphProfile::Fake || profile==GraphProfile::Observations,"graph_profile_invalid");json::Limits limits;
    if(profile==GraphProfile::Observations) {limits.bytes=786432;limits.values=32768;}
    return limits;
}
Value observation_binding(const GraphNode& node) {
    const auto& o=node.observation;
    return Value::object().put("source",Value::string(o.source)).put("capture_epoch",Value::string(std::to_string(o.capture)))
        .put("worker_epoch",Value::string(std::to_string(o.worker))).put("context_digest",Value::string(o.context_digest))
        .put("frame_digest",Value::string(o.frame_digest));
}
std::string observation_node_id(const GraphNode& node) {
    const auto& o=node.observation;
    require(node.scope==GraphNodeScope::Observation && source_id(o.source) && o.capture && o.worker &&
        digest(o.context_digest) && digest(o.frame_digest) && o.payload.kind==Value::Kind::object,"observation_binding_invalid");
    json::Limits limits;limits.bytes=16384;limits.values=1024;limits.depth=16;
    const auto bound=Value::object().put("binding",observation_binding(node)).put("kind",Value::string(node.kind))
        .put("label",Value::string(node.label)).put("payload",o.payload);
    return "observation:"+digest_sha256(json::dump(bound,limits)).substr(7);
}
std::shared_ptr<const GraphSnapshot> GraphSnapshot::create(const GraphInput& input,std::uint64_t epoch) {
    require(epoch!=0,"invalid_epoch");
    const auto limits=graph_limits(input.profile);const bool observations=input.profile==GraphProfile::Observations;
    require(input.nodes.size()<=(observations?320U:64U) && input.edges.size()<=(observations?512U:256U) && input.omissions.size()<=64,"graph_limit");
    Value nodes=Value::array(),edges=Value::array();std::set<std::string> ids;
    for(const auto& node:input.nodes) {
        require(bounded(node.id) && bounded(node.kind) && bounded(node.label,4096,true),"invalid_node");
        require(node.state=="current" || node.state=="denied" || node.state=="stale" || node.state=="unknown","invalid_state");
        require(ids.insert(node.id).second,"duplicate_node");require(node.aliases.size()<=64,"alias_limit");
        Value properties;
        if(node.scope==GraphNodeScope::Observation) {
            require(observations && node.identity.empty() && node.media_generation.empty() && node.capacity_bytes.empty() && node.aliases.empty() &&
                (node.state=="unknown" || node.state=="stale"),"observation_media_claim");
            for(auto c:node.label)require(c>=0x20 && c<=0x7e,"observation_display_invalid");
            require(node.id==observation_node_id(node),"observation_id_invalid");
            properties=Value::object().put("identity",Value{}).put("media_generation",Value{}).put("capacity_bytes",Value{})
                .put("label",Value::string(node.label)).put("state",Value::string(node.state)).put("aliases",Value::array())
                .put("scope",Value::string("observation-only")).put("physical_identity",Value::string("unknown"))
                .put("physical_admission",Value::boolean_value(false)).put("mutation_authority",Value::boolean_value(false))
                .put("freshness",Value::string(node.state=="stale"?"cached":"current_observation"))
                .put("observation_binding",observation_binding(node)).put("observation",node.observation.payload);
        } else {
            require(node.scope==GraphNodeScope::Fake && bounded(node.identity) && node.observation.source.empty(),"invalid_node");
            require(json::decimal_u64(node.media_generation) && node.media_generation!="0" &&
                (json::decimal_u64(node.capacity_bytes) || (node.capacity_bytes.empty() && node.state!="current")),"invalid_quantity");
            properties=Value::object().put("identity",Value::string(node.identity)).put("media_generation",Value::string(node.media_generation))
            .put("label",Value::string(node.label)).put("state",Value::string(node.state)).put("capacity_bytes",node.capacity_bytes.empty()?Value{}:Value::string(node.capacity_bytes))
            .put("aliases",strings(node.aliases)).put("scope",Value::string("fake-only"));
        }
        nodes.items.push_back(Value::object().put("id",Value::string(node.id)).put("kind",Value::string(node.kind))
            .put("properties",std::move(properties)).put("observation_refs",Value::array()));
    }
    for(const auto& edge:input.edges) {
        require(ids.count(edge.from) && ids.count(edge.to) && bounded(edge.kind),"invalid_edge");
        edges.items.push_back(Value::object().put("from",Value::string(edge.from)).put("to",Value::string(edge.to)).put("kind",Value::string(edge.kind)));
    }
    auto value=Value::object().put("schema",Value::string("org.disked.graph/1")).put("capture_id",Value::string((observations?"capture:":"fake:")+std::to_string(epoch)))
        .put("nodes",std::move(nodes)).put("edges",std::move(edges)).put("omissions",strings(input.omissions));
    const auto revision=digest_sha256(json::dump(value,limits));value.put("revision",Value::string(revision));
    json::dump(value,limits); // Validate the final, revision-bearing size before publication.
    return std::shared_ptr<const GraphSnapshot>(new GraphSnapshot(std::move(value),revision));
}
const Value* GraphSnapshot::node(const std::string& id) const {
    for(const auto& node:value_.find("nodes")->items)if(node.find("id")->text==id)return &node;return nullptr;
}
}
