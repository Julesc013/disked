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
Value strings(const std::vector<std::string>& items) {
    Value v=Value::array();for(const auto& item:items) {require(bounded(item),"invalid_reference");v.items.push_back(Value::string(item));}return v;
}
}
std::string digest_sha256(const std::string& bytes) {
    unsigned char digest[32];sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),digest);
    const char* hex="0123456789abcdef";std::string result="sha256:";
    for(const auto byte:digest) {result+=hex[byte>>4];result+=hex[byte&15];}return result;
}
std::shared_ptr<const GraphSnapshot> GraphSnapshot::create(const GraphInput& input,std::uint64_t epoch) {
    require(epoch!=0,"invalid_epoch");
    require(input.nodes.size()<=64 && input.edges.size()<=256 && input.omissions.size()<=64,"graph_limit");
    Value nodes=Value::array(),edges=Value::array();std::set<std::string> ids;
    for(const auto& node:input.nodes) {
        require(bounded(node.id) && bounded(node.kind) && bounded(node.identity) && bounded(node.label,4096,true),"invalid_node");
        require(json::decimal_u64(node.media_generation) && node.media_generation!="0" &&
            (json::decimal_u64(node.capacity_bytes) || (node.capacity_bytes.empty() && node.state!="current")),"invalid_quantity");
        require(node.state=="current" || node.state=="denied" || node.state=="stale" || node.state=="unknown","invalid_state");
        require(ids.insert(node.id).second,"duplicate_node");require(node.aliases.size()<=64,"alias_limit");
        auto properties=Value::object().put("identity",Value::string(node.identity)).put("media_generation",Value::string(node.media_generation))
            .put("label",Value::string(node.label)).put("state",Value::string(node.state)).put("capacity_bytes",node.capacity_bytes.empty()?Value{}:Value::string(node.capacity_bytes))
            .put("aliases",strings(node.aliases)).put("scope",Value::string("fake-only"));
        nodes.items.push_back(Value::object().put("id",Value::string(node.id)).put("kind",Value::string(node.kind))
            .put("properties",std::move(properties)).put("observation_refs",Value::array()));
    }
    for(const auto& edge:input.edges) {
        require(ids.count(edge.from) && ids.count(edge.to) && bounded(edge.kind),"invalid_edge");
        edges.items.push_back(Value::object().put("from",Value::string(edge.from)).put("to",Value::string(edge.to)).put("kind",Value::string(edge.kind)));
    }
    auto value=Value::object().put("schema",Value::string("org.disked.graph/1")).put("capture_id",Value::string("fake:"+std::to_string(epoch)))
        .put("nodes",std::move(nodes)).put("edges",std::move(edges)).put("omissions",strings(input.omissions));
    const auto revision=digest_sha256(json::dump(value));value.put("revision",Value::string(revision));
    json::dump(value); // Validate the final, revision-bearing size before publication.
    return std::shared_ptr<const GraphSnapshot>(new GraphSnapshot(std::move(value),revision));
}
const Value* GraphSnapshot::node(const std::string& id) const {
    for(const auto& node:value_.find("nodes")->items)if(node.find("id")->text==id)return &node;return nullptr;
}
}
