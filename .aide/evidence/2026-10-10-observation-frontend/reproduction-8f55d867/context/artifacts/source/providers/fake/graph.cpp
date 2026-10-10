#include "graph.h"
#include "bootstrap.h"
#include "capture.h"
#include "session.h"
#include "health_observer.h"

namespace disked {
#ifdef DISKED_CAPTURE_CAMPAIGN
// Linked only into the separate native campaign executable.
std::unique_ptr<FrontendSession> capture_campaign_session(const Registry& registry);
#endif
std::unique_ptr<FrontendSession> make_fake_session(const Registry& registry) {
#ifdef DISKED_CAPTURE_CAMPAIGN
    return capture_campaign_session(registry);
#else
    return std::unique_ptr<FrontendSession>(new FrontendSession(registry,fake_graph(),{},fake_health_observation));
#endif
}
GraphInput fake_graph() {
    initialize_fake_provider();
    GraphInput graph;
    // Serial/labels can be cloned; composite fixture identity is independent.
    graph.nodes={
        {"fake:alpha@1","block-device","fixture:controller-A:lun0","1","Workshop disk","current","1073741824",{"fake:path/A/0","fake:serial/CLONED"}},
        {"fake:clone@1","block-device","fixture:controller-B:lun0","1","Workshop disk","current","1073741824",{"fake:path/B/0","fake:serial/CLONED"}},
        {"fake:denied@1","block-device","fixture:controller-A:lun1","1","Denied observation","denied","",{}},
        {"fake:stale@1","block-device","fixture:controller-A:lun2","1","Stale observation","stale","4096",{}},
        {"fake:unknown@1","block-device","fixture:controller-A:lun3","1","Unknown observation","unknown","",{}},
        {"fake:table@1","gpt","fixture:table-A","1","Synthetic GPT","current","1073741824",{}},
        {"fake:volume@1","volume","fixture:volume-A","1","Label\x1b[31m\n\x7f\xc2\x9b\xe2\x80\xae\xe7\xa3\x81\xe7\x9b\x98\xf0\x9f\x92\xbe","current","536870912",{}}
    };
    graph.edges={{"fake:alpha@1","fake:table@1","contains"},{"fake:table@1","fake:volume@1","contains"},
        {"fake:clone@1","fake:volume@1","shared-observation"},{"fake:volume@1","fake:alpha@1","backing-reference"}};
    graph.omissions={"fake:denied@1:access_denied","fake:stale@1:observation_stale","fake:unknown@1:observation_unknown"};
    ObservationCapture capture({"provider.fake.bootstrap/1"});
    const auto key=capture.start("provider.fake.bootstrap/1");capture.finish(key,graph);
    if(capture.snapshot()->sources.front().state!=SourceState::Complete)throw std::invalid_argument("fake_capture_invalid");
    return capture.snapshot()->graph;
}
}
