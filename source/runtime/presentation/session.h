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
    FrontendSession(const Registry& registry,const GraphInput& initial,ObservationPoll observations={});
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
    std::shared_ptr<const GraphInput> observed_;
    Outcome act_cached(const FrontendAction& action);
    json::Value assessment(const std::string& target,const std::string& operation) const;
};
// ASCII-only linear view; preserves the underlying value losslessly.
std::string presentation_json(const json::Value& value,json::Limits limits = json::Limits{});
std::vector<std::string> presentation_lines(const json::Value& value,json::Limits limits = json::Limits{});
}
