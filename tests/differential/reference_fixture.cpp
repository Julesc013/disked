// Coordinator conformance fixture. NOT util-linux, a parser, or an independent
// reference implementation. Only two exact repository recipes are recognized.
#include "portable/hash/sha256.h"
#include "runtime/command/json.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

namespace {
using disked::json::Value;
const char* const disk = "12345678-9abc-4def-8123-456789abcdef";
const char* const type = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7";

Value partition(const std::string& path, unsigned slot, unsigned start,
                unsigned size, bool gpt) {
    Value value = Value::object();
    value.put("node", Value::string(path + std::to_string(slot)));
    value.put("start", Value::number(std::to_string(start)));
    value.put("size", Value::number(std::to_string(size)));
    value.put("type", Value::string(gpt ? type : slot == 1 ? "7" : "83"));
    if (gpt) value.put("uuid", Value::string(
        slot == 1 ? "00000000-0000-0000-0000-000000000001"
                  : "00000000-0000-0000-0000-000000000002"));
    return value;
}

int run(int argc, char** argv) {
    if (argc != 3 || (std::string(argv[1]) != "--json" &&
                      std::string(argv[1]) != "--verify")) return 2;
    std::ifstream input(argv[2], std::ios::binary);
    if (!input) return 2;
    // The bounded read refuses everything except the two exact authored images.
    std::vector<unsigned char> bytes(131073);
    input.read(reinterpret_cast<char*>(bytes.data()),
               static_cast<std::streamsize>(bytes.size()));
    if (input.gcount() != 131072 || !input.eof()) return 2;
    bytes.resize(131072);
    unsigned char hash[32];
    disked::sha256(bytes.data(), bytes.size(), hash);
    std::string hex;
    const char* digits = "0123456789abcdef";
    for (unsigned char byte : hash) {
        hex += digits[byte >> 4]; hex += digits[byte & 15];
    }
    const bool gpt = hex == "a851c9a2079fb74dc2eb1863f4f0885b856eb563801654e2d9e38df08844c739";
    if (!gpt && hex != "e5aa89993b9b194adc466bde8d179be24f88c02094cc4627bbe80e0bb787fa8c") return 2;
    if (std::string(argv[1]) == "--verify") {
        std::cout << "Repository protocol fixture: exact recipe recognized; no independent verification.\n";
        return 0;
    }
    Value table = Value::object();
    table.put("label", Value::string(gpt ? "gpt" : "dos"));
    table.put("unit", Value::string("sectors"));
    table.put("sectorsize", Value::number("512"));
    if (gpt) table.put("id", Value::string(disk));
    Value parts = Value::array();
    // Intentional noncontrol disagreement: 36 matches neither GPT copy (34/35).
    parts.items.push_back(partition(argv[2], 1, gpt ? 36 : 1, gpt ? 25 : 31, gpt));
    parts.items.push_back(partition(argv[2], 2, gpt ? 70 : 40, gpt ? 21 : 60, gpt));
    table.put("partitions", std::move(parts));
    Value result = Value::object(); result.put("partitiontable", std::move(table));
    std::cout << disked::json::dump(result) << '\n';
    return 0;
}
}

int main(int argc, char** argv) {
    std::cerr << "Repository-owned coordinator protocol fixture; NOT an external reference tool.\n";
    try { return run(argc, argv); }
    catch (const std::exception&) { return 2; }
}
