#pragma once
#include "definitions.h"
#include <memory>

namespace disked { namespace journal { namespace proposal {
// Closed fake-memory model, not an executor port or host durability adapter.
class GuardedModel {
    struct Impl;std::unique_ptr<Impl> state_;
public:
    GuardedModel(const Definition&,const std::vector<json::Value>& initial_receipts,const json::Value& configuration);
    ~GuardedModel();
    GuardedModel(const GuardedModel&)=delete;
    GuardedModel& operator=(const GuardedModel&)=delete;
    json::Value snapshot() const;
    json::Value history() const;
    // Bad input/illegal transition throws without changing model state.
    // Injected observation/storage failures commit an explicitly unresolved state.
    json::Value apply(const json::Value&);
};
}}}
