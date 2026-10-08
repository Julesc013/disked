#include "guarded_model.h"
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
    return V::object().put("initial",initial).put("results",results).put("final",model.snapshot()).put("history",model.history());
}
}
int main() {
    disked::json::Limits limits;limits.bytes=16777216;limits.string_bytes=2097152;limits.values=1048576;limits.depth=64;
    std::string line;while(std::getline(std::cin,line)) {
        V out;try {out=run(disked::json::parse(line,limits));}catch(const std::exception& e) {out=V::object().put("error",V::string(e.what()));}
        std::cout<<disked::json::dump(out,limits)<<'\n';
    }
}
