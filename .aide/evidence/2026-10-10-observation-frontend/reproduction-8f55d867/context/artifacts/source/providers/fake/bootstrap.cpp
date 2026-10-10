#include "bootstrap.h"
#include "bootstrap_registry.h"
#ifdef DISKED_POISON_PROVIDER
#include <cstdlib>
#endif

namespace disked {
const char* fake_provider_identity() { return bootstrap::fake_provider_id; }

void initialize_fake_provider() {
#ifdef DISKED_POISON_PROVIDER
    // The essential-command acceptance suite must never enter this boundary.
    std::_Exit(97);
#endif
    // The caller may now construct compiled graph observations. No device
    // handles, filesystem access or dynamic initialization is performed here.
}
}
