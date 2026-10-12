#include "runtime/presentation/session.h"
#include <iostream>
#include <limits>

using disked::Outcome;
using disked::PendingRequestView;
using disked::RequestDelivery;
using disked::json::Value;

namespace {
Value cases = Value::array();

void require(bool condition) {
    if (!condition) {
        throw std::runtime_error("fixture_assertion");
    }
}

template <class Action> void test(const std::string &name, Action action) {
    try {
        action();
    } catch (const std::exception &error) {
        throw std::runtime_error(name + ": " + error.what());
    }
    cases.items.push_back(Value::string(name));
}

template <class Action> void refuses(const std::string &code, Action action) {
    bool refused = false;
    try {
        action();
    } catch (const std::runtime_error &error) {
        require(error.what() == code);
        refused = true;
    }
    require(refused);
}

Outcome response(const std::string &id) {
    auto value = disked::completed(id, Value::object().put("retained", Value::string("exact")));
    value.response.put("status", Value::string("unknown"));
    value.exit_code = 6;
    return value;
}

std::string bytes(const Outcome &value) {
    return std::to_string(value.exit_code) + ":" + disked::json::dump(value.response);
}

void delivery_tests() {
    test("absent-poll", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        auto output = response("keep");
        const auto before = bytes(output);
        require(pending.poll({}, 7, output) == RequestDelivery::NoResult);
        require(pending.id() == "request:1" && bytes(output) == before);
    });
    test("not-ready-output-unchanged", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        auto output = response("keep");
        const auto before = bytes(output);
        unsigned calls = 0;
        require(pending.poll(
                    [&](Outcome &value) {
                        ++calls;
                        value = response("different");
                        return false;
                    },
                    8, output) == RequestDelivery::NoResult);
        require(calls == 1 && pending.id() == "request:1" && bytes(output) == before);
    });
    for (bool same_view : {true, false}) {
        test(same_view ? "current-view" : "earlier-view", [=] {
            PendingRequestView pending;
            pending.begin("request:1", 7);
            auto output = response("keep");
            const auto received = response("request:1");
            const auto result = pending.poll(
                [&](Outcome &value) {
                    value = received;
                    return true;
                },
                same_view ? 7 : 8, output);
            require(result ==
                    (same_view ? RequestDelivery::CurrentView : RequestDelivery::EarlierView));
            require(pending.id().empty() && bytes(output) == bytes(received));
        });
    }
    test("maximum-view-equality", [] {
        const auto maximum = (std::numeric_limits<std::uint64_t>::max)();
        for (auto view : {maximum, std::uint64_t(0)}) {
            PendingRequestView pending;
            pending.begin("request:1", maximum);
            Outcome output;
            const auto delivery = pending.poll(
                [](Outcome &value) {
                    value = response("request:1");
                    return true;
                },
                view, output);
            require(delivery == (view == maximum ? RequestDelivery::CurrentView
                                                 : RequestDelivery::EarlierView));
        }
    });
    test("wrong-identity-preserves-slot-and-output", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        auto output = response("keep");
        const auto before = bytes(output);
        refuses("frontend_completion_identity", [&] {
            pending.poll(
                [](Outcome &value) {
                    value = response("different");
                    return true;
                },
                7, output);
        });
        require(pending.id() == "request:1" && bytes(output) == before);
    });
    const std::pair<const char *, Value> invalid_ids[] = {{"null", Value{}},
                                                          {"boolean", Value::boolean_value(true)},
                                                          {"number", Value::number("1")},
                                                          {"object", Value::object()},
                                                          {"array", Value::array()},
                                                          {"empty", Value::string("")}};
    for (const auto &invalid : invalid_ids) {
        test(std::string("request-id-") + invalid.first, [&] {
            PendingRequestView pending;
            pending.begin("1", 7); // Numeric JSON1 must not match the string ID"1".
            auto output = response("keep");
            const auto before = bytes(output);
            refuses("frontend_completion_identity", [&] {
                pending.poll(
                    [&](Outcome &value) {
                        value = response("1");
                        value.response.put("request_id", invalid.second);
                        return true;
                    },
                    7, output);
            });
            require(pending.id() == "1" && bytes(output) == before);
        });
    }
    test("missing-request-id", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        auto output = response("keep");
        const auto before = bytes(output);
        refuses("frontend_completion_identity", [&] {
            pending.poll(
                [](Outcome &value) {
                    value = response("request:1");
                    value.response.fields.erase("request_id");
                    return true;
                },
                7, output);
        });
        require(pending.id() == "request:1" && bytes(output) == before);
    });
    test("unsolicited-delivery", [] {
        PendingRequestView pending;
        auto output = response("keep");
        const auto before = bytes(output);
        refuses("frontend_completion_identity", [&] {
            pending.poll(
                [](Outcome &value) {
                    value = response("request:1");
                    return true;
                },
                7, output);
        });
        require(pending.id().empty() && bytes(output) == before);
    });
    test("duplicate-delivery", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        Outcome output;
        const disked::CompletionPoll poll = [](Outcome &value) {
            value = response("request:1");
            return true;
        };
        require(pending.poll(poll, 7, output) == RequestDelivery::CurrentView);
        const auto before = bytes(output);
        refuses("frontend_completion_identity", [&] { pending.poll(poll, 7, output); });
        require(pending.id().empty() && bytes(output) == before);
    });
    test("second-pending-registration", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        refuses("frontend_pending_limit", [&] { pending.begin("request:2", 8); });
        Outcome output;
        require(pending.poll(
                    [](Outcome &value) {
                        value = response("request:1");
                        return true;
                    },
                    7, output) == RequestDelivery::CurrentView);
    });
    test("empty-registration", [] {
        PendingRequestView pending;
        refuses("frontend_completion_identity", [&] { pending.begin("", 7); });
        require(pending.id().empty());
    });
    test("old-delivery-cannot-clear-new-request", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        Outcome output;
        pending.poll(
            [](Outcome &value) {
                value = response("request:1");
                return true;
            },
            7, output);
        pending.begin("request:2", 8);
        const auto before = bytes(output);
        refuses("frontend_completion_identity", [&] {
            pending.poll(
                [](Outcome &value) {
                    value = response("request:1");
                    return true;
                },
                8, output);
        });
        require(pending.id() == "request:2" && bytes(output) == before);
    });
    test("callback-error-preserves-slot-and-output", [] {
        PendingRequestView pending;
        pending.begin("request:1", 7);
        auto output = response("keep");
        const auto before = bytes(output);
        refuses("fixture_poll_error", [&] {
            pending.poll([](Outcome &) -> bool { throw std::runtime_error("fixture_poll_error"); },
                         8, output);
        });
        require(pending.id() == "request:1" && bytes(output) == before);
    });
}

Value command(const std::string &id, Value availability = Value::string("available")) {
    return Value::object()
        .put("id", Value::string(id))
        .put("availability", std::move(availability));
}

Value discovery(Value row) {
    auto commands = Value::array();
    commands.items.push_back(std::move(row));
    return Value::object().put("commands", std::move(commands));
}

void availability_tests() {
    struct AvailabilityCase {
        const char *name;
        Value state;
        bool expected;
    };
    const AvailabilityCase states[] = {{"available", Value::string("available"), true},
                                       {"unavailable", Value::string("unavailable"), false},
                                       {"planned", Value::string("planned"), false},
                                       {"null", Value{}, false},
                                       {"boolean", Value::boolean_value(true), false},
                                       {"object", Value::object(), false}};
    for (const auto &state : states) {
        test(std::string("availability-") + state.name, [&] {
            require(disked::view_command_available(discovery(command("target.list", state.state)),
                                                   "target.list") == state.expected);
        });
    }
    for (const auto *id : {"protocol.serve", "shell.open", "shell.close", ""}) {
        test(std::string("excluded-command-") + id,
             [=] { require(!disked::view_command_available(discovery(command(id)), id)); });
    }
    test("availability-exact-identity", [] {
        const auto value = discovery(command("target.list"));
        for (const auto *id : {"target.list.extra", "TARGET.LIST", "unknown"}) {
            require(!disked::view_command_available(value, id));
        }
    });
    test("availability-duplicate-identity", [] {
        for (bool reverse : {false, true}) {
            auto commands = Value::array();
            commands.items.push_back(
                command("target.list", Value::string(reverse ? "unavailable" : "available")));
            commands.items.push_back(
                command("target.list", Value::string(reverse ? "available" : "unavailable")));
            require(!disked::view_command_available(Value::object().put("commands", commands),
                                                    "target.list"));
        }
    });
    test("availability-malformed-discovery", [] {
        for (const auto &value : {Value{}, Value::object(), Value::array(),
                                  Value::object().put("commands", Value::object())}) {
            require(!disked::view_command_available(value, "target.list"));
        }
    });
    test("availability-missing-or-mistyped-fields", [] {
        for (const auto &row :
             {Value{}, Value::object(), Value::object().put("id", Value::string("target.list")),
              Value::object()
                  .put("id", Value::number("1"))
                  .put("availability", Value::string("available"))}) {
            require(!disked::view_command_available(discovery(row), "target.list"));
        }
    });
    test("availability-compatible-background", [] {
        auto value = discovery(command("target.list").put("extension", Value::string("retained")));
        value.fields["commands"].items.push_back(Value{});
        value.put("extension", Value::object());
        require(disked::view_command_available(value, "target.list"));
    });
}
} // namespace

int main() {
    try {
        delivery_tests();
        availability_tests();
        std::cout
            << disked::json::dump(
                   Value::object().put("passed", Value::boolean_value(true)).put("cases", cases))
            << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
