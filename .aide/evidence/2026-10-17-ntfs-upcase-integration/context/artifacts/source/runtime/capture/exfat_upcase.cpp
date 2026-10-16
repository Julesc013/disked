#include "exfat_upcase.h"
#include "portable/exfat/exfat.h"
#include "portable/hash/sha256.h"
#include <algorithm>
#include <cstdint>
#include <utility>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
[[noreturn]] void stop(const char *code) {
    throw ExfatUpcaseError(code);
}
void checked(int code) {
    if (code)
        stop("exfat_internal");
}
V exact(std::uint64_t n) {
    return V::string(std::to_string(n));
}
std::string digest(const Bytes &bytes) {
    unsigned char value[32];
    sha256(bytes.data(), bytes.size(), value);
    const char digits[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (auto b : value) {
        out += digits[b >> 4];
        out += digits[b & 15];
    }
    return out;
}
std::vector<unsigned short> decode_upcase(const Bytes &bytes, de_u32 expected_checksum,
                                          bool compressed, V &facts, bool &initialized,
                                          const std::function<void(std::size_t)> &charge) {
    de_exfat_upcase state{};
    initialized = !de_exfat_upcase_init(static_cast<de_u32>(bytes.size()), expected_checksum,
                                        compressed ? 1 : 0, &state);
    if (!initialized)
        return {};
    charge(65536 * sizeof(unsigned short));
    std::vector<unsigned short> mapping(65536);
    for (std::size_t at = 0; at < bytes.size();) {
        const auto n = std::min<std::size_t>(8192, bytes.size() - at);
        const de_view view{bytes.data() + at, n};
        de_exfat_upcase_step step{};
        checked(de_exfat_upcase_feed(&state, &view, static_cast<de_u32>(at), static_cast<de_u32>(n),
                                     65536, mapping.data() + state.mapped,
                                     mapping.size() - state.mapped, &step));
        at += n;
    }
    checked(de_exfat_upcase_finish(&state));
    facts.put("bytes", exact(bytes.size()))
        .put("sha256", V::string(digest(bytes)))
        .put("checksum", exact(state.checksum))
        .put("issues", exact(state.issues))
        .put("mapped_units", exact(state.mapped))
        .put("valid", V::boolean_value(state.valid != 0));
    if (!state.valid)
        return mapping;
    // Hash the specified little-endian unit representation, not host memory.
    charge(131072);
    Bytes encoded;
    encoded.reserve(131072);
    for (auto unit : mapping) {
        encoded.push_back(static_cast<unsigned char>(unit & 255));
        encoded.push_back(static_cast<unsigned char>(unit >> 8));
    }
    facts.put("mapping_sha256", V::string(digest(encoded)));
    return mapping;
}
} // namespace
const char *exfat_upcase_format_name(ExfatUpcaseFormat format) {
    switch (format) {
    case ExfatUpcaseFormat::Compressed:
        return "compressed";
    case ExfatUpcaseFormat::Literal:
        return "literal";
    case ExfatUpcaseFormat::Automatic:
        return "auto";
    }
    throw std::invalid_argument("exfat_capture_format");
}
ExfatUpcaseFormat exfat_upcase_format_from(const std::string &format) {
    if (format == "compressed")
        return ExfatUpcaseFormat::Compressed;
    if (format == "literal")
        return ExfatUpcaseFormat::Literal;
    if (format == "auto")
        return ExfatUpcaseFormat::Automatic;
    throw std::invalid_argument("exfat_capture_format");
}
std::vector<unsigned short> evaluate_exfat_upcase(const Bytes &bytes, unsigned long checksum,
                                                  ExfatUpcaseFormat format, V &facts,
                                                  const std::function<void(std::size_t)> &charge) {
    exfat_upcase_format_name(format);
    if (bytes.size() > 262144 || checksum > 0xffffffffUL || !charge)
        throw std::invalid_argument("exfat_upcase_inputs");
    if (format != ExfatUpcaseFormat::Automatic) {
        bool initialized = false;
        auto mapping = decode_upcase(bytes, checksum, format == ExfatUpcaseFormat::Compressed,
                                     facts, initialized, charge);
        if (!initialized)
            stop("exfat_upcase_representation");
        if (!facts.fields.at("valid").boolean)
            stop("exfat_upcase_mapping");
        return mapping;
    }
    facts.put("bytes", exact(bytes.size()))
        .put("sha256", V::string(digest(bytes)))
        .put("requested_format", V::string("auto"))
        .put("selection", V::string("pending"))
        .put("valid", V::boolean_value(false))
        .put("candidates", V::array());
    std::vector<unsigned short> maps[2];
    bool valid[2] = {false, false};
    for (std::size_t index = 0; index < 2; ++index) {
        auto &candidates = facts.fields.at("candidates").items;
        candidates.push_back(V::object()
                                 .put("format", V::string(index ? "literal" : "compressed"))
                                 .put("initialized", V::boolean_value(false))
                                 .put("evaluated", V::boolean_value(false))
                                 .put("valid", V::boolean_value(false))
                                 .put("diagnostic", V{})
                                 .put("details", V::object()));
        auto &candidate = candidates.back();
        auto &initialized = candidate.fields.at("initialized").boolean;
        auto &details = candidate.fields.at("details");
        maps[index] = decode_upcase(bytes, checksum, index == 0, details, initialized, charge);
        valid[index] = initialized && details.fields.at("valid").boolean;
        candidate.put("evaluated", V::boolean_value(true))
            .put("valid", V::boolean_value(valid[index]));
        if (!initialized)
            candidate.put("diagnostic", V::string("exfat_upcase_representation"));
    }
    if (!valid[0] && !valid[1]) {
        facts.put("selection", V::string("invalid"));
        stop("exfat_upcase_mapping");
    }
    if (valid[0] && valid[1] && maps[0] != maps[1]) {
        facts.put("selection", V::string("ambiguous"));
        stop("exfat_upcase_representation_ambiguous");
    }
    const std::size_t chosen = valid[0] ? 0 : 1;
    const auto &details = facts.fields.at("candidates").items[chosen].fields.at("details");
    facts
        .put("selection", V::string(valid[0] && valid[1] ? "equivalent"
                                    : chosen             ? "literal"
                                                         : "compressed"))
        .put("valid", V::boolean_value(true))
        .put("mapping_sha256", details.fields.at("mapping_sha256"));
    return std::move(maps[chosen]);
}
ExfatUpcaseMap::ExfatUpcaseMap(Bytes bytes, std::vector<unsigned short> mapping, V facts,
                               std::string diagnostic)
    : original_(std::move(bytes)), mapping_(std::move(mapping)), facts_(std::move(facts)),
      diagnostic_(std::move(diagnostic)) {
}
ExfatUpcaseMap ExfatUpcaseMap::read(const Bytes &bytes, unsigned long checksum,
                                    ExfatUpcaseFormat format, std::size_t budget) {
    exfat_upcase_format_name(format);
    if (bytes.size() > 262144 || checksum > 0xffffffffUL || !budget || budget > 1048576)
        throw std::invalid_argument("exfat_upcase_inputs");
    V facts = V::object()
                  .put("original_bytes", exact(bytes.size()))
                  .put("original_sha256", V::string(digest(bytes)))
                  .put("original_retained", V::boolean_value(false));
    std::vector<unsigned short> mapping;
    Bytes original;
    std::string diagnostic;
    std::size_t used = 0;
    const auto charge = [&](std::size_t n) {
        if (n > budget - used)
            stop("exfat_retained_budget");
        used += n;
    };
    try {
        charge(bytes.size());
        original = bytes;
        facts.put("original_retained", V::boolean_value(true));
        mapping = evaluate_exfat_upcase(bytes, checksum, format, facts, charge);
    } catch (const ExfatUpcaseError &error) {
        diagnostic = error.what();
    }
    return ExfatUpcaseMap(std::move(original), std::move(mapping), std::move(facts),
                          std::move(diagnostic));
}
} // namespace disked
