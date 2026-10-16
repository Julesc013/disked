#include "providers/image/fat_tree_extraction.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <iostream>

using V = disked::json::Value;
static std::string text(const V &v, const char *key, const std::string &fallback = {}) {
    const auto *p = v.find(key);
    if (!p)
        return fallback;
    if (p->kind != V::Kind::string)
        throw std::runtime_error("extraction_probe_field");
    return p->text;
}
static std::uint64_t integer(const V &v, const char *key, std::uint64_t fallback = 0) {
    const auto s = text(v, key, std::to_string(fallback));
    if (!disked::json::decimal_u64(s))
        throw std::runtime_error("extraction_probe_integer");
    return std::stoull(s);
}
static void emit(V value) {
    disked::json::Limits limits;
    limits.bytes = 262144;
    limits.depth = 32;
    limits.values = 65536;
    std::cout << disked::json::dump(value, limits) << '\n' << std::flush;
}
int main() {
    try {
        const std::string data((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(data);
        disked::FatTreeExtractionRequest request;
        request.tree.path = text(input, "source");
        request.tree.volume_offset = integer(input, "offset");
        request.tree.volume_bytes = integer(input, "length");
        request.tree.capture_epoch = 17;
        const auto copy = integer(input, "copy");
        if (copy > UINT32_MAX)
            throw std::runtime_error("extraction_probe_copy");
        request.tree.fat_copy = static_cast<std::uint32_t>(copy);
        request.destination = text(input, "destination");
        request.ledger = text(input, "ledger");
        request.metadata.name_selection = text(input, "name_selection", "long_or_short");
        request.metadata.unrepresentable_name = text(input, "unrepresentable_name", "refuse");
        const auto code_page = integer(input, "oem_code_page", 437);
        if (code_page > UINT32_MAX)
            throw std::runtime_error("extraction_probe_page");
        request.metadata.oem_code_page = static_cast<std::uint32_t>(code_page);
        request.metadata.time_interpretation = text(input, "time_interpretation", "preserve_raw");
        const auto offset = text(input, "utc_offset_minutes", "0");
        std::size_t used = 0;
        request.metadata.utc_offset_minutes = std::stoi(offset, &used);
        if (used != offset.size())
            throw std::runtime_error("extraction_probe_offset");
        request.entries = static_cast<std::size_t>(integer(input, "entries", 65536));
        request.directories = static_cast<std::size_t>(integer(input, "directories", 4096));
        request.metadata_bytes =
            static_cast<std::size_t>(integer(input, "metadata_bytes", 16777216));
        request.pages = static_cast<std::size_t>(integer(input, "pages", 65536));
        request.content_bytes = integer(input, "content_bytes", 1099511627776ULL);
        request.ledger_bytes = integer(input, "ledger_bytes", 1073741824);
        disked::FatTreeExtraction operation(request);
        emit(V::object()
                 .put("kind", V::string("prepared"))
                 .put("definition", operation.definition())
                 .put("digest", V::string(operation.digest())));
        if (text(input, "mode", "execute") == "prepare")
            return 0;
        if (text(input, "race") == "destination") {
            const auto path = disked::json::utf16_units(request.destination);
            std::wstring selected(path.begin(), path.end());
            if (!CreateDirectoryW(selected.c_str(), nullptr))
                throw std::runtime_error("fixture race create");
        }
        disked::FatTreeExtractionGrant grant;
        grant.definition_digest = text(input, "wrong_digest").empty()
                                      ? operation.digest()
                                      : "sha256:" + std::string(64, '0');
        grant.source_read = grant.destination_write = grant.ledger_write = grant.host_effects =
            true;
        const auto missing = text(input, "missing_grant");
        if (missing == "source")
            grant.source_read = false;
        if (missing == "destination")
            grant.destination_write = false;
        if (missing == "ledger")
            grant.ledger_write = false;
        if (missing == "host")
            grant.host_effects = false;
        disked::FatTreeExtractionHooks hooks;
        hooks.attempt_id = "generated-fixture-attempt:1";
        bool cancelled = false;
        unsigned matches = 0;
        hooks.stop = [&] { return cancelled; };
        hooks.boundary = [&](const char *boundary) {
            if (text(input, "race") == "child" && std::string(boundary) == "root_created") {
                const auto path = disked::json::utf16_units(request.destination + "/00000000.BIN");
                std::wstring selected(path.begin(), path.end());
                HANDLE file = CreateFileW(selected.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
                                          FILE_ATTRIBUTE_NORMAL, nullptr);
                if (file == INVALID_HANDLE_VALUE)
                    throw std::runtime_error("fixture child race create");
                const char marker[] = "external-fixture-marker";
                DWORD got = 0;
                const bool wrote =
                    WriteFile(file, marker, sizeof(marker) - 1, &got, nullptr) != FALSE;
                CloseHandle(file);
                if (!wrote || got != sizeof(marker) - 1)
                    throw std::runtime_error("fixture child race write");
            }
            if (text(input, "cancel_boundary") == boundary ||
                text(input, "exit_boundary") == boundary ||
                text(input, "throw_boundary") == boundary) {
                ++matches;
                if (matches == integer(input, "boundary_number", 1)) {
                    if (text(input, "exit_boundary") == boundary)
                        ExitProcess(93);
                    if (text(input, "throw_boundary") == boundary)
                        throw std::runtime_error("fixture-effect-fault");
                    cancelled = true;
                }
            }
        };
        emit(V::object()
                 .put("kind", V::string("outcome"))
                 .put("value", operation.execute(grant, hooks)));
        try {
            operation.execute(grant, hooks);
            throw std::runtime_error("repeated execution accepted");
        } catch (const disked::FatTreeExtractionError &error) {
            if (std::string(error.what()) != "fat_tree_extract_already_executed")
                throw;
        }
        return 0;
    } catch (const std::exception &error) {
        emit(V::object().put("kind", V::string("error")).put("code", V::string(error.what())));
        return 0;
    }
}
