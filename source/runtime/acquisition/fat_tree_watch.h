#pragma once
#include "fat_tree_operation.h"
#include <functional>

namespace disked {
namespace fat_tree_operation {
using EventSink = std::function<bool(const json::Value &)>;
void validate_watch_options(const json::Value &);
// Cursor sequences count admitted control records; stored record indices remain
// zero-based. The exact immutable header and retained prefix bind one observer.
class Watch final {
    std::string operation_, request_, observer_, worker_, header_digest_, review_digest_, digest_;
    std::size_t sequence_ = 0, events_ = 0, event_bytes_ = 0;
    bool snapshot_ = false, closed_ = false, initialized_ = false;

  public:
    Watch(const std::string &operation, const std::string &request, const std::string &observer,
          const json::Value &options);
    bool project(const History &, const EventSink &);
    json::Value cursor() const;
};
// Compatible observational reader. Outer/payload additions stay with callers;
// retained mutation-critical records and required features remain strict.
class Reader final {
    json::Value header_;
    std::vector<json::Value> records_;
    std::string header_digest_, digest_, observer_, request_;
    std::size_t sequence_ = 0;
    bool snapshot_allowed_ = false, snapshot_mode_ = false;

  public:
    explicit Reader(const json::Value &header, bool snapshot_allowed = false);
    bool accept(const json::Value &event);
    json::Value cursor() const;
};
} // namespace fat_tree_operation
} // namespace disked
