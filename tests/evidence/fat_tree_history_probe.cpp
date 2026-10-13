#include "runtime/evidence/fat_tree_history.h"
#include <algorithm>
#include <iostream>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int main(int argc, char **argv) {
    try {
#ifdef _WIN32
        if (_setmode(_fileno(stdin), _O_BINARY) == -1)
            throw std::runtime_error("history_probe_binary_input");
#endif
        std::size_t chunk = 8192;
        disked::evidence::proposal::FatTreeHistoryBudget budget;
        for (int i = 1; i < argc; i += 2) {
            if (i + 1 == argc || !disked::json::decimal_u64(argv[i + 1]))
                throw std::runtime_error("history_probe_argument");
            const auto value = std::stoull(argv[i + 1]);
            const std::string name = argv[i];
            if (name == "--chunk") {
                if (!value || value > 262144)
                    throw std::runtime_error("history_probe_chunk");
                chunk = static_cast<std::size_t>(value);
            } else if (name == "--bytes")
                budget.bytes = value;
            else if (name == "--entries") {
                if (value > 65536)
                    throw std::runtime_error("history_probe_entries");
                budget.entries = static_cast<std::size_t>(value);
            } else if (name == "--records") {
                if (value > 2000000)
                    throw std::runtime_error("history_probe_records");
                budget.records = static_cast<std::size_t>(value);
            } else
                throw std::runtime_error("history_probe_argument");
        }
        disked::evidence::proposal::FatTreeHistory history(budget);
        std::string bytes(chunk, '\0');
        while (std::cin) {
            std::cin.read(&bytes[0], static_cast<std::streamsize>(chunk));
            const auto count = std::cin.gcount();
            if (count)
                history.consume(bytes.substr(0, static_cast<std::size_t>(count)));
        }
        if (!std::cin.eof())
            throw std::runtime_error("history_probe_input");
        std::cout << disked::json::dump(history.finish()) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cout << disked::json::dump(disked::json::Value::object().put(
                         "error", disked::json::Value::string(e.what())))
                  << '\n';
        return 20;
    }
}
