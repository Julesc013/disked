#pragma once
#include "fat_traversal.h"
#include "runtime/command/protocol.h"
#include <mutex>

namespace disked {
struct FatTreeOpenRequest {
    std::string path;
    std::uint64_t volume_offset = 0, volume_bytes = 0, epoch = 0;
    std::uint32_t fat_copy = 0;
    FatTraversalResources resources;
    FatTraversalPageBudget page;
};
struct FatTreePacket {
    json::Value frame, context;
};
struct FatTreePoll {
    std::shared_ptr<const FatTreePacket> packet;
    json::Value worker;
};
// Private provider port. Its concrete owner qualifies process/source provenance;
// these copied observations confer no authority on an imported JSON value.
class FatTreeCursor {
  public:
    virtual ~FatTreeCursor() = default;
    virtual json::Value source() const = 0;
    virtual FatTreePoll poll() = 0;
    virtual json::Value observe() = 0;
    virtual json::Value stop(bool retire) = 0;
};
using FatTreeCursorFactory =
    std::function<std::unique_ptr<FatTreeCursor>(const FatTreeOpenRequest &)>;
class FatTreeSessionError : public std::runtime_error {
  public:
    const std::uint32_t platform_code;
    explicit FatTreeSessionError(const char *code, std::uint32_t platform = 0)
        : std::runtime_error(code), platform_code(platform) {
    }
};
class FatTreeSessions final {
    struct Entry;
    const std::function<std::string()> domain_source_;
    const FatTreeCursorFactory factory_;
    std::mutex mutex_;
    std::string domain_;
    std::uint64_t sequence_ = 0;
    std::map<std::string, std::shared_ptr<Entry>> entries_;
    Outcome dispatch_impl(const std::string &, const json::Value &, bool stream_owner);

  public:
    FatTreeSessions(std::function<std::string()>, FatTreeCursorFactory);
    ~FatTreeSessions();
    FatTreeSessions(const FatTreeSessions &) = delete;
    FatTreeSessions &operator=(const FatTreeSessions &) = delete;
    Outcome dispatch(const std::string &request, const json::Value &parameters);
    Outcome stream(const std::string &request, const json::Value &parameters,
                   const ResponseSink &output);
    static constexpr std::size_t slots = 4, record_bytes = 2U * 1024U * 1024U, chunk_bytes = 196608;
};
bool valid_fat_tree_session_id(const std::string &);
} // namespace disked
