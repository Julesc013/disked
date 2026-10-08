#pragma once
#include "definitions.h"

namespace disked { namespace journal { namespace proposal {
struct PublisherBinding {Identity identity{};std::uint64_t epoch=0;};
struct SemanticScan {Scan framing;std::string semantic_diagnostic;json::Value projection;};
// Expected plan/header/publisher are established outside the untrusted source.
// Checks declarations only. No live observations, effects or recovery decisions.
SemanticScan scan_semantics(Source&,const Definition&,const Bindings&,const PublisherBinding&);
}}}
