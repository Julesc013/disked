#pragma once
#include "snapshot.h"
namespace disked {
struct Registry;class FrontendSession;
GraphInput fake_graph();
std::unique_ptr<FrontendSession> make_fake_session(const Registry& registry);
}
