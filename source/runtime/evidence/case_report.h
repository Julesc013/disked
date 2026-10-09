#pragma once
#include "health.h"
#include <memory>
namespace disked { namespace evidence { namespace proposal {
struct Error : std::runtime_error {explicit Error(const char* code):std::runtime_error(code){}};
json::Limits case_limits();
// Private fixture contract, not a persisted/public case ABI. One coordinator
// records immutable snapshots; recording does not dispatch or retire observers.
class Case final {
public:
    Case(const std::string& case_id,const json::Value& code_identity);
    void append(const std::string& phase,const std::string& origin,
        const std::string& fixture_digest,const health::proposal::Capture& capture);
    json::Value view() const;
    json::Value support(const json::Value& policy) const;
    std::string digest() const;
private:
    struct Entry {json::Value record;std::shared_ptr<const health::proposal::Capture> snapshot;};
    std::string id_,context_;
    json::Value code_;
    std::vector<Entry> entries_;
    bool closed_=false;
    json::Value full(const std::vector<Entry>& entries,bool closed) const;
    json::Value project(const std::vector<Entry>& entries,bool closed,const json::Value& policy) const;
};
}}}
