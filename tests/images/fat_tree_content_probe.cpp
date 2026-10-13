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
        disked::FatTreeFile source(input);
        std::uint64_t files = 0, pages = 0;
        while (!source.finished()) {
            auto frame = source.next();
            const auto events = field(field(frame, "page"), "events");
            emit(V::object().put("kind", V::string("tree")).put("frame", std::move(frame)));
            for (const auto &event : events.items) {
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
