#include "definitions.h"
#include <iostream>

namespace p=disked::journal::proposal;
using V=disked::json::Value;
namespace {
const V& field(const V& v,const char* name) {const auto f=v.find(name);if(!f)throw p::DefinitionError("probe_field");return *f;}
V inspect(V input) {
    auto plan=field(input,"plan");const p::Definition definition(plan);
    auto values=field(input,"receipts");if(values.kind!=V::Kind::array)throw p::DefinitionError("probe_receipts");
    auto receipts=V::array();for(const auto& v:values.items) {
        const p::Receipt receipt(definition,v);
        receipts.items.push_back(V::object().put("payload",V::string(std::string(receipt.payload().begin(),receipt.payload().end())))
            .put("digest",V::string(p::digest_text(receipt.digest()))));
    }
    const auto checked=p::inspect_receipts(definition,values.items);
    bool immutable=true;
    if(input.find("freeze") && field(input,"freeze").boolean) {
        const auto original=definition.payload();plan.put("id",V::string("changed.input"));plan.fields.clear();
        immutable=definition.payload()==original && !definition.value().fields.empty();
        if(!values.items.empty()) {
            const p::Receipt receipt(definition,values.items.front());const auto retained=receipt.payload();
            values.items.front().fields.clear();immutable=immutable && receipt.payload()==retained && !receipt.value().fields.empty();
        }
    }
    return V::object().put("payload",V::string(std::string(definition.payload().begin(),definition.payload().end())))
        .put("digest",V::string(p::digest_text(definition.digest()))).put("resources_digest",V::string(p::digest_text(definition.resources_digest())))
        .put("providers_digest",V::string(p::digest_text(definition.providers_digest()))).put("recovery_summary",definition.recovery_summary())
        .put("receipt_payloads",receipts).put("inspection",checked).put("caller_input_immutable",V::boolean_value(immutable))
        .put("file_io",V::boolean_value(false));
}
}
int main() {
    disked::json::Limits limits;limits.bytes=2097152;limits.string_bytes=2097152;limits.values=65536;limits.depth=64;
    std::string line;while(std::getline(std::cin,line)) {
        V out;
        try {out=inspect(disked::json::parse(line,limits));}
        catch(const p::DefinitionError& e) {auto witness=V::array();for(const auto& s:e.witness)witness.items.push_back(V::string(s));out=V::object().put("error",V::string(e.what())).put("witness",witness);}
        catch(const std::exception& e) {out=V::object().put("error",V::string(e.what()));}
        std::cout<<disked::json::dump(out,limits)<<'\n';
    }
}
