#include "bootstrap_registry.h"
#include "bootstrap.h"
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <string>
#include <vector>

namespace {
int refuse(const char* code, const char* message, int status) {
    std::fprintf(stderr, "disked: %s: %s\n", code, message);
    return status;
}
int invalid() { return refuse("invalid_arguments", "invalid bootstrap arguments", 2); }
int unavailable() { return refuse("command_unavailable", "command is unavailable in this composition", 3); }
int finish() {
    if (std::fflush(stdout) != 0 || std::ferror(stdout))
        return refuse("output_error", "unable to write output", 4);
    return 0;
}
bool unsupported_option(const wchar_t* value) {
    const std::wstring spelling(value, std::wcscspn(value, L"="));
    for (const auto* option : bootstrap::unavailable_options)
        if (spelling == option) return true;
    return false;
}
void help() {
    std::puts("DiskEd native bootstrap (fake-only; human output only)\n"
        "Usage: disked build inspect | command list | commands | help [command]\n"
        "Static help: --help or -h before, between or after command words.\n"
        "Storage, GUI, TUI, shell and machine output are unavailable.");
}
void build_info() {
    using namespace bootstrap;
    std::printf("product=%s\nversion=%s\nsource_revision=%s\nsource_state=%s\n"
        "input_digest=%s\ntarget=%s\ncomposition=%s\ncompiler=%s\nsdk=%s\n"
        "configuration=%s\nlanguage=%s\ncrt=%s\nconfiguration_digest=%s\nfake_provider=%s\n",
        product, version, source_revision, source_state, input_digest, target, composition,
        compiler, sdk, configuration, language, crt, configuration_digest, disked::fake_provider_identity());
}
void command_list() {
    std::puts("id\tcontract_status\timplementation_status\tavailability\treason\tcommand");
    for (const auto& command : bootstrap::commands)
        std::printf("%s\tplanned\t%s\t%s\t%s\t%s\n", command.id,
            command.implemented ? "implemented" : "planned",
            command.implemented ? "available" : "unavailable",
            command.implemented ? "bootstrap_human_only" : "not_implemented", command.form);
}
}

int wmain(int argc, wchar_t** argv) {
    // Validate this bounded surface in full before printing or dispatching.
    std::vector<std::wstring> words;
    bool literal = false, help_requested = false, invalid_input = false, unsupported = false;
    std::size_t command_boundary = 0;
    for (int i = 1; i < argc; ++i) {
        const wchar_t* token = argv[i];
        if (!literal && std::wcscmp(token, L"--") == 0) {
            command_boundary = words.size(); literal = true; continue;
        }
        if (!literal && (std::wcscmp(token, L"--help") == 0 || std::wcscmp(token, L"-h") == 0)) {
            if (help_requested) invalid_input = true;
            help_requested = true;
        } else if (!literal && token[0] == L'-') {
            if (unsupported_option(token)) unsupported = true;
            else invalid_input = true;
        } else words.emplace_back(token);
    }
    if (!literal) command_boundary = words.size();
    if (command_boundary > 0 && words[0] == L"help") {
        if (help_requested) invalid_input = true;
        help_requested = true;
        words.erase(words.begin()); --command_boundary;
    }
    if (invalid_input) return invalid();
    if (unsupported) return refuse("feature_unavailable", "control is unavailable in this composition", 3);
    if (words.empty()) { help(); return finish(); }

    const bootstrap::Command* selected = nullptr;
    std::size_t consumed = 0;
    std::wstring candidate;
    for (std::size_t n = 0; n < command_boundary; ++n) {
        if (n) candidate += L' ';
        candidate += words[n];
        for (const auto& form : bootstrap::forms) {
            if (n + 1 == form.words && candidate == form.text) { selected = &bootstrap::commands[form.command]; consumed = n + 1; }
        }
    }
    if (!selected) return unavailable();
    if ((selected->implemented || help_requested) && consumed != words.size()) return invalid();
    if (help_requested) {
        std::printf("%s: %s\ncommand: %s\navailability: %s\n", selected->id, selected->summary,
            selected->form, selected->implemented ? "available (bootstrap human subset)" : "unavailable (planned)");
    } else if (!selected->implemented) return unavailable();
    else if (std::strcmp(selected->id, "build.inspect") == 0) build_info();
    else if (std::strcmp(selected->id, "command.list") == 0) command_list();
    else return unavailable();
    return finish();
}
