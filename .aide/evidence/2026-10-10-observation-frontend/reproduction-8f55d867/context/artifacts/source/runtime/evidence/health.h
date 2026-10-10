#pragma once
#include "json.h"
#include <cstdint>

namespace disked { namespace health { namespace proposal {
// Private serialized reducer, not a public ABI or admitted hardware observer.
// A single owning coordinator serializes calls; adapters cannot reenter it.
struct Error : std::runtime_error {explicit Error(const char* code):std::runtime_error(code){}};
struct Ticket {std::string source;std::uint64_t capture=0,worker=0;};
json::Value ticket_value(const Ticket& key);
Ticket read_ticket(const json::Value& value);
class Capture final {
public:
    // Counter seeds are a private boundary-test seam, not persisted authority.
    explicit Capture(const json::Value& request,std::uint64_t capture=1,std::uint64_t worker_seed=0);
    Ticket start(const std::string& source);
    bool finish(const Ticket& key,const json::Value& response);
    bool timeout(const Ticket& key);
    // Only the actual adapter's separately observed exit permits retirement.
    // This call records a declaration; the reducer does not observe OS workers.
    bool retire(const Ticket& key);
    bool cancel();
    void next_capture();
    json::Value view() const;
    json::Value support(const json::Value& policy) const;
private:
    struct Slot {
        json::Value declaration,fields;
        std::string state,diagnostic;
        std::uint64_t worker=0;
        bool started=false,open=false,live=false;
    };
    json::Value target_;
    std::vector<Slot> slots_;
    std::uint64_t capture_;
    bool cancelled_=false;
    std::size_t slot(const std::string& source) const;
    bool matches(const Slot& slot,const Ticket& key) const;
    std::string state() const;
    void reset(Slot& slot);
};
}}}
