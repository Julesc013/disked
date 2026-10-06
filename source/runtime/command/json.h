#pragma once
#include <cstddef>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace disked { namespace json {
struct Limits {
    std::size_t bytes = 65536;
    std::size_t depth = 32;
    std::size_t values = 8192;
    std::size_t string_bytes = 32768;
};
struct Error : std::runtime_error {
    std::string code;
    std::size_t offset;
    Error(const std::string& name, std::size_t position);
};
// Private native representation; not a public ABI or a storage serialization.
struct Value {
    enum class Kind { null, boolean, number, string, array, object };
    Kind kind = Kind::null;
    bool boolean = false;
    std::string text;
    std::vector<Value> items;
    std::map<std::string, Value> fields;
    static Value string(const std::string& value);
    static Value number(const std::string& exact_lexeme);
    static Value boolean_value(bool value);
    static Value array();
    static Value object();
    const Value* find(const std::string& key) const;
    Value& put(const std::string& key, Value value);
};
bool valid_utf8(const std::string& text);
bool decimal_u64(const std::string& text);
Value parse(const std::string& input, Limits limits = Limits{});
std::string dump(const Value& value, Limits limits = Limits{});
}}
