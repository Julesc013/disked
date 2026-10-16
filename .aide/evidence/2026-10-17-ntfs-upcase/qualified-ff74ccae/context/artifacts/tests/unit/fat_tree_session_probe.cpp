#include "runtime/capture/fat_tree_session.h"
#include <atomic>
#include <future>
#include <iostream>
#include <thread>

using namespace disked;
using V = json::Value;
namespace {
int checks = 0;
void require(bool value) {
    ++checks;
    if (!value)
        throw std::runtime_error("tree_session_probe_failed");
}
V number(std::uint64_t n) {
    return V::string(std::to_string(n));
}
struct Control {
    bool exit = false, corrupt = false;
    int stops = 0, polls = 0;
};
class FakeCursor : public FatTreeCursor {
    std::shared_ptr<Control> control_;
    std::uint64_t sequence_ = 0;
    std::string digest_;

  public:
    explicit FakeCursor(std::shared_ptr<Control> c) : control_(std::move(c)) {
    }
    V source() const override {
        return V::object().put("source", V::string("supplied-fixture"));
    }
    V observe() override {
        return V::object()
            .put("status", V::string(control_->exit ? "completed" : "observing"))
            .put("worker",
                 V::object().put("observation", V::string(control_->exit ? "exited" : "running")));
    }
    V stop(bool) override {
        ++control_->stops;
        return observe();
    }
    FatTreePoll poll() override {
        ++control_->polls;
        auto page = V::object()
                        .put("schema", V::string("org.disked.fat-traversal-page/1"))
                        .put("sequence", number(++sequence_))
                        .put("binding", V::object().put("fixture", V::string("same")))
                        .put("previous_page_digest", digest_.empty() ? V{} : V::string(digest_));
        page.put("status", V::string("running"));
        digest_ = fat_traversal_page_digest(page);
        page.put("page_digest",
                 V::string(control_->corrupt ? "sha256:" + std::string(64, '0') : digest_));
        auto packet = std::make_shared<const FatTreePacket>(
            FatTreePacket{V::object().put("source_before", source()).put("page", std::move(page)),
                          V::object().put("fixture_only", V::boolean_value(true))});
        return {packet, observe()};
    }
};
V open() {
    return V::object()
        .put("phase", V::string("open"))
        .put("path", V::string("fixture"))
        .put("volume_offset", number(0))
        .put("volume_bytes", number(512));
}
V call(const char *phase, const std::string &id) {
    return V::object().put("phase", V::string(phase)).put("session_id", V::string(id));
}
const V &result(const Outcome &o) {
    return o.response.fields.at("result");
}
} // namespace
int main() {
    try {
        auto control = std::make_shared<Control>();
        std::atomic<int> opens{0};
        FatTreeSessions sessions([] { return std::string(32, 'a'); },
                                 [&](const FatTreeOpenRequest &) {
                                     ++opens;
                                     return std::unique_ptr<FatTreeCursor>(new FakeCursor(control));
                                 });
        for (const auto key :
             {"page_records", "page_events", "page_reads", "page_read_bytes", "page_output_bytes",
              "bitmap_bytes", "queued_directories", "depth"}) {
            auto p = open();
            p.put(key, number(UINT64_MAX));
            require(sessions.dispatch("invalid", p).exit_code == 2 && opens == 0);
        }
        auto bad = open();
        bad.put("volume_offset", number(UINT64_MAX));
        require(sessions.dispatch("overflow", bad).exit_code == 2 && opens == 0);
        bad = open();
        bad.put("invented", V::boolean_value(true));
        require(sessions.dispatch("unknown", bad).exit_code == 2 && opens == 0);
        const auto opened = sessions.dispatch("open", open());
        require(opened.exit_code == 0 && opens == 1);
        const auto id = result(opened).fields.at("session_id").text;
        require(valid_fat_tree_session_id(id));
        require(valid_fat_tree_session_id("fat-tree:" + std::string(32, 'a') +
                                          ":18446744073709551615"));
        require(!valid_fat_tree_session_id("fat-tree:" + std::string(32, 'a') + ":0"));
        require(!valid_fat_tree_session_id("fat-tree:" + std::string(32, 'a') +
                                           ":18446744073709551616"));
        const auto first = sessions.dispatch("page1", call("next", id));
        require(first.exit_code == 0 &&
                result(first).fields.at("page").fields.at("sequence").text == "1");
        auto read = call("read", id)
                        .put("page_sequence", number(1))
                        .put("byte_offset", number(0))
                        .put("byte_count", number(196608));
        const auto old = sessions.dispatch("bytes1", read);
        require(old.exit_code == 0 && result(old).fields.at("next_offset").kind == V::Kind::null);
        require(sessions.dispatch("page2", call("next", id)).exit_code == 0);
        require(sessions.dispatch("stale", read).exit_code == 3);
        read.put("page_sequence", number(2));
        const auto historical = sessions.dispatch("bytes2", read);
        require(historical.exit_code == 0);
        control->corrupt = true;
        require(sessions.dispatch("corrupt", call("next", id)).exit_code == 6);
        require(control->stops == 1);
        require(result(sessions.dispatch("historical", read)).fields.at("data").text ==
                result(historical).fields.at("data").text);
        const auto polls = control->polls;
        require(sessions.dispatch("poisoned", call("next", id)).exit_code == 6 &&
                control->polls == polls);
        control->corrupt = false;
        for (int i = 0; i < 3; ++i)
            require(sessions.dispatch("more", open()).exit_code == 0);
        require(sessions.dispatch("capacity", open()).exit_code == 3 && opens == 4);
        require(result(sessions.dispatch("closing", call("close", id))).fields.at("state").text ==
                "closing");
        require(sessions.dispatch("still-owned", open()).exit_code == 3 && opens == 4);
        control->exit = true;
        require(result(sessions.dispatch("closed", call("close", id))).fields.at("state").text ==
                "closed");
        require(sessions.dispatch("removed", call("status", id)).exit_code == 3);
        require(sessions.dispatch("reuse", open()).exit_code == 0 && opens == 5);

        // An actual concurrent open keeps its reservation while the port waits.
        std::promise<void> entered, release;
        const auto released = release.get_future().share();
        FatTreeSessions pending([] { return std::string(32, 'b'); },
                                [&](const FatTreeOpenRequest &) {
                                    entered.set_value();
                                    released.wait();
                                    return std::unique_ptr<FatTreeCursor>(new FakeCursor(control));
                                });
        Outcome delayed;
        std::thread worker([&] { delayed = pending.dispatch("delayed", open()); });
        entered.get_future().wait();
        const auto list = pending.dispatch("list", V::object());
        const auto pending_id =
            result(list).fields.at("sessions").items[0].fields.at("session_id").text;
        const auto busy = pending.dispatch("busy", call("next", pending_id));
        release.set_value();
        worker.join();
        require(busy.exit_code == 3 && delayed.exit_code == 0);
        require(result(list).fields.at("sessions").items[0].fields.at("state").text == "busy");
        FatTreeSessions streamed([] { return std::string(32, 'c'); },
                                 [&](const FatTreeOpenRequest &) {
                                     return std::unique_ptr<FatTreeCursor>(new FakeCursor(control));
                                 });
        auto scan = open().put("phase", V::string("scan")).put("max_pages", number(1));
        int events = 0;
        const auto budgeted = streamed.stream("stream", scan, [&](const V &value) {
            ++events;
            const auto &body = value.fields.at("result");
            if (body.fields.at("event_kind").text == "opened")
                require(
                    streamed.dispatch("foreign", call("next", body.fields.at("session_id").text))
                        .exit_code == 3);
            return true;
        });
        require(budgeted.exit_code == 6 && events == 3);
        require(result(budgeted).fields.at("closure").fields.at("state").text == "closed");
        require(
            result(streamed.dispatch("empty", V::object())).fields.at("sessions").items.empty());
        const auto disconnected = streamed.stream("broken", scan, [](const V &) { return false; });
        require(disconnected.exit_code == 4);
        require(
            result(streamed.dispatch("empty", V::object())).fields.at("sessions").items.empty());
        std::cout << "{\"passed\":true,\"checks\":" << checks
                  << ",\"scope\":\"supplied-port-session-rules\"}\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
