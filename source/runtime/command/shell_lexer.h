#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace disked {
struct ShellToken {std::string value;std::size_t begin=0,end=0;};
struct ShellLine {
    std::vector<ShellToken> tokens;
    std::string error;
    std::size_t error_byte=0;
    bool open_quote=false;
    std::vector<std::string> arguments() const;
};
// Private frontend tokenizer. No expansions or operating-system execution.
ShellLine tokenize_shell(const std::string& line,bool completion=false);
std::string quote_shell(const std::string& token);
}
