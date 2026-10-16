#pragma once
#include "runtime/command/json.h"
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace disked {
enum class ExfatUpcaseFormat { Compressed, Literal, Automatic };
const char *exfat_upcase_format_name(ExfatUpcaseFormat);
ExfatUpcaseFormat exfat_upcase_format_from(const std::string &);

struct ExfatUpcaseError : std::runtime_error {
    explicit ExfatUpcaseError(const char *code) : std::runtime_error(code) {
    }
};
// Shared private decoder selection. Facts retain completed candidates when a
// later charge/decoder fails. The caller owns the input through the whole call.
std::vector<unsigned short> evaluate_exfat_upcase(const std::vector<unsigned char> &,
                                                  unsigned long checksum, ExfatUpcaseFormat,
                                                  json::Value &facts,
                                                  const std::function<void(std::size_t)> &charge);

// Immutable supplied-table interpretation, not source identity or opening rights.
class ExfatUpcaseMap final {
    const std::vector<unsigned char> original_;
    const std::vector<unsigned short> mapping_;
    const json::Value facts_;
    const std::string diagnostic_;
    ExfatUpcaseMap(std::vector<unsigned char>, std::vector<unsigned short>, json::Value,
                   std::string);

  public:
    static ExfatUpcaseMap read(const std::vector<unsigned char> &, unsigned long checksum,
                               ExfatUpcaseFormat, std::size_t retained_budget = 786432);
    bool valid() const {
        return diagnostic_.empty() && mapping_.size() == 65536;
    }
    const std::vector<unsigned char> &original() const {
        return original_;
    }
    const std::vector<unsigned short> &mapping() const {
        return mapping_;
    }
    const json::Value &facts() const {
        return facts_;
    }
    const std::string &diagnostic() const {
        return diagnostic_;
    }
};
} // namespace disked
