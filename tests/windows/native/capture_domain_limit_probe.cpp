#include "capture.h"
#include <cstdio>
#include <type_traits>

static_assert(!std::is_copy_constructible<disked::ObservationCapture>::value && !std::is_move_constructible<disked::ObservationCapture>::value,"no forked counter stream");
static_assert(!std::is_copy_constructible<disked::CaptureEpochDomain>::value && !std::is_move_constructible<disked::CaptureEpochDomain>::value,"no cloned epoch domain");
int main(int argc,char**) {
    if(argc!=1)return 2;
    using V=disked::json::Value;auto reasons=V::array();
    for(unsigned i=0;i<2;++i) {
        try{disked::ObservationCapture capture({"source"});return 7;}
        catch(const std::invalid_argument& e){if(std::string(e.what())!="capture_domain_limit")return 7;reasons.items.push_back(V::string(e.what()));}
    }
    auto value=V::object().put("schema",V::string("org.disked.private-capture-domain-limit-probe/1"))
        .put("pointer_bytes",V::string(std::to_string(sizeof(void*))))
        .put("initial_ordinal",V::string("18446744073709551615")).put("reasons",reasons)
        .put("coordinator_created",V::boolean_value(false)).put("mutation_authority",V::boolean_value(false));
    std::puts(disked::json::dump(value).c_str());return 0;
}
