#pragma once
#include <cstddef>
#include <cstdint>

namespace disked {
// One-shot SHA-256 for bounded in-memory observations. No authentication claim.
void sha256(const unsigned char* data, std::size_t size, unsigned char digest[32]);
}
