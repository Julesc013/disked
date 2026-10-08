#pragma once
#include "codec.h"
#include "json.h"
#include <utility>

namespace disked { namespace journal { namespace proposal {
struct DefinitionError:Error {
    std::vector<std::string> witness;
    explicit DefinitionError(const std::string& code,std::vector<std::string> cycle={}):Error(code),witness(std::move(cycle)) {}
};
// Private fake-model values. No target/file/authority/flush ports.
class Definition {
    json::Value value_,summary_;
    Bytes payload_;Digest digest_{},resources_{},providers_{};
public:
    explicit Definition(const json::Value&);
    const json::Value& value() const {return value_;}
    const json::Value& recovery_summary() const {return summary_;}
    const Bytes& payload() const {return payload_;}
    Digest digest() const {return digest_;}
    Digest resources_digest() const {return resources_;}
    Digest providers_digest() const {return providers_;}
};
class Receipt {
    json::Value value_;Bytes payload_;Digest digest_{};
public:
    Receipt(const Definition&,const json::Value&);
    const json::Value& value() const {return value_;}
    const Bytes& payload() const {return payload_;}
    Digest digest() const {return digest_;}
};
std::string digest_text(const Digest&);
// Validate immutable identities, references, scope and per-attempt sequence.
// Matching fixture data is never operator authentication or effect authority.
json::Value inspect_receipts(const Definition&,const std::vector<json::Value>&);
}}}
