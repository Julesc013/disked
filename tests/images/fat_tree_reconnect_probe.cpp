#include "platform/windows/storage/fat_tree_reconnect.h"
#include "runtime/acquisition/fat_tree_operation.h"
#include <iostream>

using V = disked::json::Value;
static const V &get(const V &v, const char *k) {
    const auto *p = v.find(k);
    if (!p)
        throw std::runtime_error("reconnect_probe_shape");
    return *p;
}
int main() {
    try {
        auto limits = disked::fat_tree_operation::header_limits();
        limits.bytes = 2097152;
        limits.string_bytes = 1048576;
        const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(raw, limits);
        disked::fat_tree_operation::EventSink native_sink;
        if (const auto *stream = input.find("stream_watch"))
            if (stream->boolean)
                native_sink = [&](const V &event) {
                    std::cout << disked::json::dump(event, limits) << '\n' << std::flush;
                    return static_cast<bool>(std::cout);
                };
        V result;
        if (const auto *h = input.find("header")) {
            if (const auto *supplied_events = input.find("reader_events")) {
                disked::fat_tree_operation::Reader reader(*h, input.find("snapshot") &&
                                                                  input.find("snapshot")->boolean);
                auto results = V::array();
                for (const auto &event : supplied_events->items) {
                    auto row = V::object();
                    try {
                        row.put("accepted", V::boolean_value(reader.accept(event)));
                    } catch (const std::exception &e) {
                        row.put("error", V::string(e.what()));
                    }
                    results.items.push_back(row.put("cursor", reader.cursor()));
                }
                result = V::object().put("results", results).put("cursor", reader.cursor());
            } else if (const auto *options = input.find("watch")) {
                disked::fat_tree_operation::Watch watcher(
                    get(*h, "operation_id").text, "probe-request", "watch:" + std::string(32, 'a'),
                    *options);
                auto events = V::array(), steps = V::array();
                const auto sink = [&](const V &event) {
                    if (const auto *count = input.find("stop_after"))
                        if (events.items.size() >= std::stoull(count->text))
                            return false;
                    if (const auto *count = input.find("throw_after"))
                        if (events.items.size() >= std::stoull(count->text))
                            throw std::runtime_error("probe_sink_failed");
                    events.items.push_back(event);
                    return true;
                };
                const auto project = [&](const V &header, const std::string &raw) {
                    auto step = V::object();
                    try {
                        step.put("open",
                                 V::boolean_value(watcher.project(
                                     disked::fat_tree_operation::read_history(header, raw), sink)));
                    } catch (const std::exception &e) {
                        step.put("error", V::string(e.what()));
                    }
                    steps.items.push_back(step.put("cursor", watcher.cursor()));
                };
                if (const auto *batches = input.find("batches")) {
                    for (const auto &batch : batches->items)
                        project(batch.find("header") ? *batch.find("header") : *h,
                                get(batch, "history").text);
                } else
                    project(*h, get(input, "history").text);
                result = V::object()
                             .put("events", events)
                             .put("steps", steps)
                             .put("cursor", watcher.cursor());
            } else
                result =
                    disked::fat_tree_operation::read_history(*h, get(input, "history").text).view();
        } else if (const auto *options = input.find("watch")) {
            result = disked::nt_inventory::watch_fat_tree_operation(
                get(input, "operation_id").text, get(input, "store").text, *options, native_sink);
        } else if (const auto *ms = input.find("wait_ms")) {
            if (!disked::json::decimal_u64(ms->text) || std::stoull(ms->text) > UINT32_MAX)
                throw std::runtime_error("probe_wait_integer");
            result = disked::nt_inventory::wait_fat_tree_operation(
                get(input, "operation_id").text, get(input, "store").text,
                static_cast<std::uint32_t>(std::stoull(ms->text)), native_sink);
        } else
            result = disked::nt_inventory::observe_fat_tree_operation(
                get(input, "operation_id").text, get(input, "store").text,
                input.find("cancel") && input.find("cancel")->boolean);
        std::cout << disked::json::dump(result, limits) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cout << disked::json::dump(V::object().put("error", V::string(e.what()))) << '\n';
        return 20;
    }
}
