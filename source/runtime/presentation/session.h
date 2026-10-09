#pragma once
#include "snapshot.h"
#include "protocol.h"
#include "requests.h"

namespace disked {
enum class ActionKind {Inspect, Select, ClearSelection};
struct FrontendAction {ActionKind kind;std::string target_id,expected_revision,request_id;};
// Serialized, in-memory fake observation service. Frontends never derive
// storage eligibility from rows. Observation polling is nonblocking and
// serialized here; producer threads never access this session.
class FrontendSession final {
public:
    // The source returns a retained immutable snapshot. A publication failure
    // must not acknowledge/consume it; the same pointer remains eligible later.
    using ObservationPoll=std::function<std::shared_ptr<const GraphInput>()>;
    // A composition selects this bounded observation port. Selection/revision
    // checks stay in the coordinator; the port receives only the retained node.
    using HealthObservation=std::function<Outcome(const std::string&,const json::Value&,const std::string&,const json::Value&)>;
    FrontendSession(const Registry& registry,const GraphInput& initial,ObservationPoll observations={},HealthObservation health={});
    std::shared_ptr<const GraphSnapshot> snapshot() {refresh_observations();return snapshot_;}
    bool refresh_observations();
    void publish(const GraphInput& input);
    json::Value selection() const;
    Outcome act(const FrontendAction& action);
    Outcome dispatch(const std::string& request,const std::string& command,
        const json::Value& parameters,const std::string& expected_revision="");
    static bool handles(const std::string& command);
private:
    const Registry& registry_;
    std::uint64_t epoch_=0;
    std::shared_ptr<const GraphSnapshot> snapshot_;
    std::map<std::string,std::string> identities_;
    std::string selected_;
    ObservationPoll observations_;
    HealthObservation health_;
    std::shared_ptr<const GraphInput> observed_;
    Outcome act_cached(const FrontendAction& action);
    json::Value assessment(const std::string& target,const std::string& operation) const;
};
// ASCII-only linear view; preserves the underlying value losslessly.
std::string presentation_json(const json::Value& value,json::Limits limits = json::Limits{});
std::vector<std::string> presentation_lines(const json::Value& value,json::Limits limits = json::Limits{},std::size_t display_bytes=1048576);
std::vector<std::string> observation_lines(const json::Value& value);
}
