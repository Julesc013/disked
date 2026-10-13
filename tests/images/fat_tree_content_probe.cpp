#include "providers/image/fat_tree_file.h"
#include "providers/image/local_file.h"
#include <iostream>
using V = disked::json::Value;
namespace f = disked::local_file;
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::runtime_error("tree content probe field");
    return *p;
}
static std::uint64_t integer(const V &v, const char *key) {
    const auto &x = field(v, key);
    if (x.kind != V::Kind::string || !disked::json::decimal_u64(x.text))
        throw std::runtime_error("tree content probe integer");
    return std::stoull(x.text);
}
static void emit(V v) {
    std::cout << disked::json::dump(v, disked::fat_tree_content_json_limits()) << '\n'
              << std::flush;
}
int main() {
    try {
        const std::string bytes((std::istreambuf_iterator<char>(std::cin)), {});
        const auto value = disked::json::parse(bytes, disked::fat_tree_content_json_limits());
        disked::FatTreeInput input;
        input.path = field(value, "path").text;
        input.capture_epoch = 17;
        input.volume_offset = integer(value, "offset");
        input.volume_bytes = integer(value, "length");
        const auto copy = value.find("copy") ? integer(value, "copy") : 0;
        if (copy > UINT32_MAX)
            throw std::runtime_error("tree content probe copy");
        input.fat_copy = static_cast<std::uint32_t>(copy);
        const auto path = f::path_for(input.path);
        auto parents = f::pin_parents(path);
        const auto generations = f::parent_generations(parents);
        f::Handle handle(
            CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (handle.value == INVALID_HANDLE_VALUE)
            throw f::Error("tree_content_probe_open", GetLastError());
        f::ordinary(handle.value, false);
        f::bind_path(handle.value, path);
        f::check_parents(path, parents, generations);
        input.expected_source = f::metadata(handle.value).value;
        if (const auto *fixture = value.find("fixture"))
            input.fixture = *fixture;
        if (value.find("small_pages")) {
            input.page.records = 1;
            input.page.events = 1;
        }
        disked::FatTreeFile source(input);
        std::uint64_t files = 0, pages = 0;
        std::string previous_key;
        while (!source.finished()) {
            auto frame = source.next();
            const auto events = field(field(frame, "page"), "events");
            emit(V::object().put("kind", V::string("tree")).put("frame", std::move(frame)));
            if (value.find("metadata_only") && !previous_key.empty()) {
                try {
                    source.metadata_candidates(previous_key, {});
                    throw std::runtime_error("previous metadata page accepted");
                } catch (const std::invalid_argument &error) {
                    if (std::string(error.what()) != "fat_tree_metadata_not_observed")
                        throw;
                }
                previous_key.clear();
            }
            for (const auto &event : events.items) {
                if (value.find("metadata_only")) {
                    if (field(event, "type").text != "record" ||
                        (field(event, "kind").text != "3" && field(event, "kind").text != "4") ||
                        field(event, "dot").text != "0")
                        continue;
                    const auto key = field(event, "key").text;
                    disked::FatMetadataPolicy policy;
                    policy.oem_code_page = 437;
                    if (value.find("identity_names"))
                        policy.name_selection = "identity";
                    try {
                        source.metadata_candidates("entry:0", policy);
                        throw std::runtime_error("unknown metadata membership accepted");
                    } catch (const std::invalid_argument &error) {
                        if (std::string(error.what()) != "fat_tree_metadata_not_observed")
                            throw;
                    }
                    const bool cancelled = value.find("cancel_metadata") != nullptr;
                    try {
                        auto metadata = source.metadata_candidates(
                            key, policy, [cancelled] { return cancelled; });
                        if (cancelled)
                            throw std::runtime_error("cancelled metadata accepted");
                        emit(V::object()
                                 .put("kind", V::string("metadata"))
                                 .put("frame", std::move(metadata)));
                        ++files;
                    } catch (const std::invalid_argument &error) {
                        if (!cancelled ||
                            std::string(error.what()) != "fat_tree_metadata_cancelled")
                            throw;
                        emit(V::object()
                                 .put("kind", V::string("metadata_refused"))
                                 .put("code", V::string(error.what())));
                    }
                    previous_key = key;
                    continue;
                }
                if (field(event, "type").text != "record" || field(event, "kind").text != "3")
                    continue;
                const auto key = field(event, "key").text;
                try {
                    source.start_content("entry:0");
                    throw std::runtime_error("unknown membership accepted");
                } catch (const std::invalid_argument &e) {
                    if (std::string(e.what()) != "fat_tree_content_not_observed")
                        throw;
                }
                source.start_content(key);
                ++files;
                if (!source.content_finished()) {
                    try {
                        source.next();
                        throw std::runtime_error("busy traversal accepted");
                    } catch (const std::invalid_argument &e) {
                        if (std::string(e.what()) != "fat_tree_content_busy")
                            throw;
                    }
                }
                while (!source.content_finished()) {
                    const bool cancel =
                        value.find("cancel_after") && pages >= integer(value, "cancel_after");
                    auto content = source.next_content({}, [cancel] { return cancel; });
                    ++pages;
                    emit(V::object()
                             .put("kind", V::string("content"))
                             .put("key", V::string(key))
                             .put("frame", std::move(content)));
                }
            }
        }
        emit(V::object()
                 .put("kind", V::string("summary"))
                 .put("files", V::string(std::to_string(files)))
                 .put("content_pages", V::string(std::to_string(pages))));
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
