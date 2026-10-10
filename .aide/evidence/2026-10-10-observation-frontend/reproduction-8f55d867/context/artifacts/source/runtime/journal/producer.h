#pragma once
#include "semantics.h"

namespace disked { namespace journal { namespace proposal {
struct ProducedJournal {
    Bytes bytes;
    std::uint64_t stable_bytes=0;
    SemanticScan inspection;
};
// Private projection of closed-model histories into proposed binary declarations.
// Retains rejected bytes. No append/flush/file/authority or recovery port.
std::vector<ProducedJournal> produce_model_history(const Definition&,const json::Value& history,const Bindings&,const PublisherBinding&);
}}}
