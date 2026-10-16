#pragma once

namespace disked {
// Private bootstrap boundary, not a public SDK/provider ABI.
const char* fake_provider_identity();
void initialize_fake_provider();
}
