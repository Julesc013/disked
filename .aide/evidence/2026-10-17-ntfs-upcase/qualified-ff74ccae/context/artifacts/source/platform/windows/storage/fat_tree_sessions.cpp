#include "fat_tree_sessions.h"
#include "fat_tree_worker.h"
#include "providers/image/local_file.h"
#include "platform/windows/worker_files.h"

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace f = local_file;
bool exited(const V &value) {
    const auto *worker = value.find("worker");
    const auto *state = worker ? worker->find("observation") : nullptr;
    return state && state->kind == V::Kind::string && state->text == "exited";
}
class Cursor final : public FatTreeCursor {
    const std::wstring path_;
    std::vector<f::Handle> parents_;
    const V generations_;
    f::Handle file_;
    V source_;
    std::unique_ptr<FatTreeWorker> worker_;

  public:
    explicit Cursor(const FatTreeOpenRequest &r)
        : path_(f::path_for(r.path)), parents_(f::pin_parents(path_)),
          generations_(f::parent_generations(parents_)),
          file_(CreateFileW(path_.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr)) {
        if (file_.value == INVALID_HANDLE_VALUE)
            throw f::Error("fat_source_open", GetLastError());
        f::ordinary(file_.value, false);
        f::bind_path(file_.value, path_);
        f::check_parents(path_, parents_, generations_);
        source_ = f::metadata(file_.value).value;
        FatTreeInput input;
        input.path = r.path;
        input.expected_source = source_;
        input.capture_epoch = r.epoch;
        input.volume_offset = r.volume_offset;
        input.volume_bytes = r.volume_bytes;
        input.fat_copy = r.fat_copy;
        input.resources = r.resources;
        input.page = r.page;
#ifdef DISKED_FAT_TREE_COMMAND_TESTING
        for (const auto &item : {std::pair<const wchar_t *, const char *>{
                                     L"DISKED_FAT_TREE_COMMAND_TEST_WORKER", "worker_fault"},
                                 {L"DISKED_FAT_TREE_COMMAND_TEST_REPLY", "reply_fault"},
                                 {L"DISKED_FAT_TREE_COMMAND_TEST_STARTUP", "startup_fault"}}) {
            wchar_t value[64];
            const auto count = GetEnvironmentVariableW(item.first, value, 64);
            if (count >= 64)
                throw FatTreeSessionError("tree_session_fixture");
            if (count)
                input.fixture.put(item.second, V::string(f::utf8(value)));
        }
#endif
        worker_ = FatTreeWorker::prepare(input);
    }
    void launch() {
        worker_->launch();
        // The child still validates its input/image and establishes containment
        // before collection. Release must not depend on human UI response time.
        worker_->release();
    }
    ~Cursor() override {
        if (!worker_ || worker_->never_launched())
            return;
        // No callback, page or source dependency escapes this owned reader.
        // The original source is read-only; teardown never replays its work.
        V observed;
        try {
            worker_->cancel();
            observed = worker_->retire();
        } catch (...) {
        }
        while (!exited(observed)) {
            try {
                observed = worker_->observe(100);
            } catch (...) {
                Sleep(100);
            }
        }
    }
    V source() const override {
        return source_;
    }
    V observe() override {
        return worker_->observe();
    }
    FatTreePoll poll() override {
        FatTreePoll out;
        if (const auto page = worker_->next_page()) {
            out.packet = std::make_shared<const FatTreePacket>(
                FatTreePacket{page->frame(), page->context()});
        }
        out.worker = worker_->observe();
        return out;
    }
    V stop(bool retire) override {
        if (retire) {
            const auto observed = worker_->observe();
            if (exited(observed))
                return observed;
        }
        worker_->cancel();
        return retire ? worker_->retire(0) : worker_->observe();
    }
};
} // namespace
std::unique_ptr<FatTreeCursor> open_fat_tree_cursor(const FatTreeOpenRequest &r) {
    try {
        std::unique_ptr<Cursor> cursor(new Cursor(r));
        cursor->launch();
        return std::unique_ptr<FatTreeCursor>(std::move(cursor));
    } catch (const f::Error &e) {
        throw FatTreeSessionError(e.what(), e.platform_code);
    } catch (const worker_files::Failure &e) {
        throw FatTreeSessionError(e.what(), e.platform);
    } catch (const std::exception &e) {
        throw FatTreeSessionError(e.what());
    }
}
} // namespace nt_inventory
} // namespace disked
