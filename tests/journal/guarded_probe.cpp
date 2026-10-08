#include "guarded_model.h"
#ifdef DISKED_MODEL_BINARY_PROJECTION
#include "producer.h"
#endif
#include <iostream>

using V=disked::json::Value;
namespace p=disked::journal::proposal;
namespace {
const V& get(const V& v,const char* k) {const auto x=v.find(k);if(!x)throw p::DefinitionError("probe_field");return *x;}
V run(const V& v) {
    const auto& actions=get(v,"actions");const auto& receipts=get(v,"receipts");
    if(actions.kind!=V::Kind::array || actions.items.size()>1024)throw p::DefinitionError("probe_action_limit");
    if(receipts.kind!=V::Kind::array)throw p::DefinitionError("probe_receipts");
    const p::Definition definition(get(v,"plan"));p::GuardedModel model(definition,receipts.items,get(v,"configuration"));
    const auto initial=model.snapshot();auto results=V::array();
    for(const auto& action:actions.items) {
        auto row=V::object();
        try {row.put("snapshot",model.apply(action)).put("accepted",V::boolean_value(true)).put("error",V::string(""));}
        catch(const std::exception& e) {row.put("snapshot",model.snapshot()).put("accepted",V::boolean_value(false)).put("error",V::string(e.what()));}
        results.items.push_back(row);
    }
    auto output=V::object().put("initial",initial).put("results",results).put("final",model.snapshot()).put("history",model.history());
#ifdef DISKED_MODEL_BINARY_PROJECTION
    p::Bindings bindings;bindings.journal.fill(0x31);bindings.plan=definition.digest();bindings.targets=definition.resources_digest();bindings.providers=definition.providers_digest();
    p::PublisherBinding publisher;publisher.identity.fill(0x41);publisher.epoch=1;auto journals=V::array();
    const auto override=v.find("history_override");
    for(const auto& produced:p::produce_model_history(definition,override?*override:model.history(),bindings,publisher)) {
        std::string bytes;for(const auto b:produced.bytes) {bytes.push_back("0123456789abcdef"[b>>4]);bytes.push_back("0123456789abcdef"[b&15]);}
        const auto& s=produced.inspection;
        journals.items.push_back(V::object().put("bytes",V::string(bytes)).put("stable_bytes",V::string(std::to_string(produced.stable_bytes)))
            .put("projection",s.projection).put("disposition",V::string(s.framing.disposition)).put("diagnostic",V::string(s.framing.diagnostic))
            .put("semantic_diagnostic",V::string(s.semantic_diagnostic)).put("records",V::string(std::to_string(s.framing.records)))
            .put("verified_bytes",V::string(std::to_string(s.framing.verified_bytes))));
    }output.put("binary_history",journals);
#endif
    return output;
}
}
int main() {
    disked::json::Limits limits;limits.bytes=16777216;limits.string_bytes=2097152;limits.values=1048576;limits.depth=64;
#ifdef DISKED_MODEL_BINARY_PROJECTION
    limits.bytes=33554432;limits.string_bytes=4194304;
#endif
    std::string line;while(std::getline(std::cin,line)) {
        V out;try {out=run(disked::json::parse(line,limits));}catch(const std::exception& e) {out=V::object().put("error",V::string(e.what()));}
        std::cout<<disked::json::dump(out,limits)<<'\n';
    }
}
