#include "fat_tree_controller.h"
#include "fat_tree_admission.h"
#include "platform/windows/worker_files.h"
#include <cstring>

namespace disked {
namespace nt_inventory {
namespace {
using V = json::Value;
namespace w = worker_files;
constexpr std::size_t input_bytes = 524288, output_bytes = 32768;
struct Input {
    DWORD length;
    char bytes[input_bytes];
};
struct Output {
    volatile LONG sequence;
    DWORD length;
    char digest[64], bytes[output_bytes];
};
struct View {
    void *value;
    View(HANDLE h, DWORD access, std::size_t size) : value(MapViewOfFile(h, access, 0, 0, size)) {
        if (!value)
            w::fail("fat_tree_controller_mapping");
    }
    ~View() {
        UnmapViewOfFile(value);
    }
};
[[noreturn]] void invalid(const char *code) {
    throw std::invalid_argument(code);
}
const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        invalid("fat_tree_controller_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::string)
        invalid("fat_tree_controller_shape");
    return p.text;
}
void keys(const V &v, std::initializer_list<const char *> names) {
    if (v.kind != V::Kind::object || v.fields.size() != names.size())
        invalid("fat_tree_controller_shape");
    for (auto k : names)
        field(v, k);
}
bool boolean(const V &v, const char *key) {
    const auto &p = field(v, key);
    if (p.kind != V::Kind::boolean)
        invalid("fat_tree_controller_shape");
    return p.boolean;
}
V grant_value(const FatTreeReviewGrant &g) {
    return V::object()
        .put("review_digest", V::string(g.review_digest))
        .put("source_read", V::boolean_value(g.source_read))
        .put("destination_write", V::boolean_value(g.destination_write))
        .put("ledger_write", V::boolean_value(g.ledger_write))
        .put("operation_write", V::boolean_value(g.operation_write))
        .put("host_effects", V::boolean_value(g.host_effects));
}
FatTreeReviewGrant grant_from(const V &v) {
    keys(v, {"review_digest", "source_read", "destination_write", "ledger_write", "operation_write",
             "host_effects"});
    return {text(v, "review_digest"),        boolean(v, "source_read"),
            boolean(v, "destination_write"), boolean(v, "ledger_write"),
            boolean(v, "operation_write"),   boolean(v, "host_effects")};
}
DWORD stall_budget(const V &fixture) {
    if (fixture.kind != V::Kind::object)
        invalid("fat_tree_controller_fixture");
    DWORD ms = 30000;
#ifndef DISKED_FAT_TREE_CONTROLLER_TESTING
    if (!fixture.fields.empty())
        invalid("fat_tree_controller_fixture_not_compiled");
#else
    for (const auto &item : fixture.fields) {
        if (item.second.kind != V::Kind::string)
            invalid("fat_tree_controller_fixture");
        if (item.first == "controller_stall_ms") {
            if (!json::decimal_u64(item.second.text))
                invalid("fat_tree_controller_fixture");
            const auto n = std::stoull(item.second.text);
            if (n < 100 || n > 5000)
                invalid("fat_tree_controller_fixture");
            ms = static_cast<DWORD>(n);
        } else if (item.first == "controller_fault" && item.second.text == "exit_after_admitted") {
            continue;
        } else if (item.first != "worker_fault" && item.first != "startup_fault")
            invalid("fat_tree_controller_fixture");
    }
#endif
    return ms;
}
json::Limits output_limits() {
    auto l = fat_tree_review_limits();
    l.bytes = output_bytes;
    return l;
}
w::Handle mapping(const w::Security &s, std::size_t n) {
    auto a = s.attributes;
    w::Handle h(CreateFileMappingW(INVALID_HANDLE_VALUE, &a, PAGE_READWRITE, 0,
                                   static_cast<DWORD>(n), nullptr));
    if (!h.valid())
        w::fail("fat_tree_controller_mapping_create");
    return h;
}
w::Handle event(const w::Security &s) {
    auto a = s.attributes;
    w::Handle h(CreateEventW(&a, TRUE, FALSE, nullptr));
    if (!h.valid())
        w::fail("fat_tree_controller_event_create");
    return h;
}
void job_check(HANDLE job, bool member) {
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION l{};
    const DWORD flags = JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                        JOB_OBJECT_LIMIT_JOB_MEMORY;
    if (!QueryInformationJobObject(job, JobObjectExtendedLimitInformation, &l, sizeof(l),
                                   nullptr) ||
        l.BasicLimitInformation.LimitFlags != flags ||
        l.BasicLimitInformation.ActiveProcessLimit != 2 ||
        l.ProcessMemoryLimit != 128 * 1024 * 1024 || l.JobMemoryLimit != 256 * 1024 * 1024)
        invalid("fat_tree_controller_job");
    BOOL in = FALSE;
    if (member && (!IsProcessInJob(GetCurrentProcess(), job, &in) || !in))
        invalid("fat_tree_controller_job");
}
V process_identity() {
    return V::object()
        .put("pid", V::string(std::to_string(GetCurrentProcessId())))
        .put("created", V::string(w::process_created(GetCurrentProcess())));
}
V reply(const V &input, const std::string &phase, const V &admission,
        const std::string &diagnostic) {
    const auto *id = admission.find("operation_id");
    return V::object()
        .put("schema", V::string("org.disked.fat-tree-controller-reply-prototype/1"))
        .put("input_digest",
             V::string("sha256:" + w::hash(json::dump(input, fat_tree_review_limits()))))
        .put("code_sha256", field(input, "code_sha256"))
        .put("host_id", field(input, "host_id"))
        .put("review_digest", field(field(input, "grant"), "review_digest"))
        .put("controller", process_identity())
        .put("phase", V::string(phase))
        .put("operation_id", id ? *id : V{})
        .put("admission", admission)
        .put("diagnostic", diagnostic.empty() ? V{} : V::string(diagnostic));
}
void publish(Output *out, const V &value) {
    const auto bytes = json::dump(value, output_limits()), digest = w::hash(bytes);
    InterlockedIncrement(&out->sequence);
    out->length = static_cast<DWORD>(bytes.size());
    std::memcpy(out->bytes, bytes.data(), bytes.size());
    std::memcpy(out->digest, digest.data(), 64);
    MemoryBarrier();
    InterlockedIncrement(&out->sequence);
}
bool exited(const V &admission) {
    return text(field(field(admission, "worker"), "worker"), "observation") == "exited";
}
bool quiescent(const V &admission) {
    const auto observation = text(field(field(admission, "worker"), "worker"), "observation");
    return observation == "exited" || observation == "not_started";
}
} // namespace

struct FatTreeController::Impl {
    w::Security security;
    w::Image image;
    w::Directory code_parent;
    w::WorkerBudget aggregate;
    w::Handle input, output, gate, abandon, job, process;
    std::unique_ptr<View> view;
    V binding;
    std::string digest, created;
    DWORD pid = 0;
    bool launch_attempted = false, dispatched = false;
    Impl(const FatTreeReview &r, const FatTreeReviewGrant &g, const V &fixture)
        : code_parent(w::narrow(image.path.substr(0, image.path.find_last_of(L'\\')))),
          aggregate(security, true) {
        const auto &code = field(
            field(field(field(r.definition, "backend"), "resources"), "executable"), "observed");
        if (text(code, "path") != w::narrow(image.path) ||
            text(code, "sha256") != "sha256:" + image.digest)
            invalid("fat_tree_controller_code_changed");
        binding = V::object()
                      .put("schema", V::string("org.disked.fat-tree-controller-input-prototype/1"))
                      .put("review", r.definition)
                      .put("grant", grant_value(g))
                      .put("fixture", fixture)
                      .put("host_id", V::string(security.host_id))
                      .put("code_sha256", V::string(image.digest));
        const auto raw = json::dump(binding, fat_tree_review_limits());
        if (raw.size() > input_bytes)
            invalid("fat_tree_controller_input_budget");
        digest = "sha256:" + w::hash(raw);
        input = mapping(security, sizeof(Input));
        output = mapping(security, sizeof(Output));
        {
            View v(input.value, FILE_MAP_WRITE, sizeof(Input));
            auto *p = static_cast<Input *>(v.value);
            p->length = static_cast<DWORD>(raw.size());
            std::memcpy(p->bytes, raw.data(), raw.size());
        }
        view.reset(new View(output.value, FILE_MAP_READ, sizeof(Output)));
        gate = event(security);
        abandon = event(security);
        auto a = security.attributes;
        job = w::Handle(CreateJobObjectW(&a, nullptr));
        if (!job.valid())
            w::fail("fat_tree_controller_job_create");
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION l{};
        l.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                                             JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                                             JOB_OBJECT_LIMIT_JOB_MEMORY;
        l.BasicLimitInformation.ActiveProcessLimit = 2;
        l.ProcessMemoryLimit = 128 * 1024 * 1024;
        l.JobMemoryLimit = 256 * 1024 * 1024;
        if (!SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &l, sizeof(l)))
            w::fail("fat_tree_controller_job_create");
        job_check(job.value, false);
    }
};
FatTreeController::FatTreeController(std::unique_ptr<Impl> p) : impl_(std::move(p)) {
}
FatTreeController::~FatTreeController() {
    if (impl_ && !impl_->dispatched && impl_->abandon.valid())
        SetEvent(impl_->abandon.value);
}
std::unique_ptr<FatTreeController>
FatTreeController::prepare(const FatTreeReview &r, const FatTreeReviewGrant &g, const V &fixture) {
    validate_fat_tree_review_grant(r, g);
    stall_budget(fixture);
    return std::unique_ptr<FatTreeController>(
        new FatTreeController(std::unique_ptr<Impl>(new Impl(r, g, fixture))));
}
void FatTreeController::launch() {
    auto &p = *impl_;
    if (p.launch_attempted)
        invalid("fat_tree_controller_launch_reused");
    p.launch_attempted = true;
    auto ci = w::inherited(p.input.value, FILE_MAP_READ),
         co = w::inherited(p.output.value, FILE_MAP_WRITE),
         cg = w::inherited(p.gate.value, SYNCHRONIZE),
         ca = w::inherited(p.abandon.value, SYNCHRONIZE),
         cp = w::inherited(GetCurrentProcess(), SYNCHRONIZE),
         cj = w::inherited(p.job.value, JOB_OBJECT_QUERY),
         cb = w::inherited(p.aggregate.job.value, JOB_OBJECT_QUERY);
    std::vector<HANDLE> handles = {ci.value, co.value, cg.value, ca.value,
                                   cp.value, cj.value, cb.value},
                        jobs = {p.aggregate.job.value, p.job.value};
    w::AttributeList attributes(handles, jobs);
    STARTUPINFOEXW startup{};
    startup.StartupInfo.cb = sizeof(startup);
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.lpAttributeList = attributes.list;
    startup.StartupInfo.hStdInput = INVALID_HANDLE_VALUE;
    startup.StartupInfo.hStdOutput = INVALID_HANDLE_VALUE;
    startup.StartupInfo.hStdError = INVALID_HANDLE_VALUE;
    std::wstring command = L"\"" + p.image.path + L"\" __disked_fat_tree_controller";
    for (auto h : handles)
        command += L" " + std::to_wstring(reinterpret_cast<std::uintptr_t>(h));
    p.code_parent.check();
    PROCESS_INFORMATION raw{};
    if (!CreateProcessW(p.image.path.c_str(), &command[0], nullptr, nullptr, TRUE,
                        DETACHED_PROCESS | EXTENDED_STARTUPINFO_PRESENT, nullptr,
                        p.code_parent.path.c_str(), &startup.StartupInfo, &raw))
        w::fail("fat_tree_controller_spawn");
    p.process = w::Handle(raw.hProcess);
    w::Handle thread(raw.hThread);
    p.pid = raw.dwProcessId;
    p.created = w::process_created(p.process.value);
}
void FatTreeController::dispatch() {
    auto &p = *impl_;
    if (!p.process.valid() || p.dispatched)
        invalid("fat_tree_controller_dispatch_reused");
    if (!SetEvent(p.gate.value))
        w::fail("fat_tree_controller_dispatch");
    p.dispatched = true;
}
V FatTreeController::observe(DWORD wait_ms) {
    if (wait_ms > 1000)
        invalid("fat_tree_controller_wait_budget");
    auto &p = *impl_;
    DWORD wait = p.process.valid() ? WaitForSingleObject(p.process.value, wait_ms) : WAIT_FAILED;
    auto out =
        V::object()
            .put("schema", V::string("org.disked.fat-tree-controller-observation-prototype/1"))
            .put("status",
                 V::string(p.dispatched ? wait == WAIT_TIMEOUT ? "dispatch_pending" : "unknown"
                                        : "not_dispatched"))
            .put("operation_id", V{})
            .put("controller",
                 V::object()
                     .put("pid", V::string(std::to_string(p.pid)))
                     .put("created", V::string(p.created))
                     .put("observation", V::string(!p.process.valid()      ? "not_started"
                                                   : wait == WAIT_TIMEOUT  ? "running"
                                                   : wait == WAIT_OBJECT_0 ? "exited"
                                                                           : "unavailable")))
            .put("reply", V{})
            .put("diagnostic", V{});
    try {
        const auto *v = static_cast<const Output *>(p.view->value);
        MemoryBarrier();
        const auto before = v->sequence;
        if (!before || before % 2)
            return out;
        const auto n = v->length;
        if (!n || n > output_bytes)
            invalid("fat_tree_controller_publication");
        const std::string bytes(v->bytes, n), digest(v->digest, 64);
        MemoryBarrier();
        if (v->sequence != before)
            return out;
        if (w::hash(bytes) != digest)
            invalid("fat_tree_controller_publication");
        const auto r = json::parse(bytes, output_limits());
        keys(r, {"schema", "input_digest", "code_sha256", "host_id", "review_digest", "controller",
                 "phase", "operation_id", "admission", "diagnostic"});
        if (text(r, "schema") != "org.disked.fat-tree-controller-reply-prototype/1" ||
            text(r, "input_digest") != p.digest || text(r, "code_sha256") != p.image.digest ||
            text(r, "host_id") != p.security.host_id ||
            text(r, "review_digest") != text(field(p.binding, "grant"), "review_digest") ||
            text(field(r, "controller"), "pid") != std::to_string(p.pid) ||
            text(field(r, "controller"), "created") != p.created)
            invalid("fat_tree_controller_reply_binding");
        const auto phase = text(r, "phase");
        if (phase != "admitted" && phase != "finished" && phase != "refused" &&
            phase != "unresolved")
            invalid("fat_tree_controller_reply_phase");
        const auto &id = field(r, "operation_id");
        if (phase == "admitted" || phase == "finished") {
            if (id.kind != V::Kind::string || id.text.size() != 40 ||
                id.text.compare(0, 8, "tree-op:") ||
                id.text.find_first_not_of("0123456789abcdef", 8) != id.text.npos)
                invalid("fat_tree_controller_reply_identity");
        }
        out.put("operation_id", id)
            .put("reply", r)
            .put("status", V::string(phase == "admitted"   ? "accepted_running"
                                     : phase == "finished" ? "completed"
                                     : phase == "refused"  ? "refused"
                                                           : "unknown"));
        if (phase == "admitted" && wait != WAIT_TIMEOUT)
            out.put("status", V::string("unknown"))
                .put("diagnostic", V::string("fat_tree_controller_exit_unresolved"));
    } catch (const std::exception &e) {
        out.put("status", V::string("unknown")).put("diagnostic", V::string(e.what()));
    }
    if (wait == WAIT_OBJECT_0 && field(out, "reply").kind == V::Kind::null)
        out.put("status", V::string("unknown"));
    return out;
}
int fat_tree_controller_role(int argc, wchar_t **argv) {
    if (argc != 9)
        return 2;
    try {
        w::Handle hi(w::argument_handle(argv[2])), ho(w::argument_handle(argv[3])),
            hg(w::argument_handle(argv[4])), ha(w::argument_handle(argv[5])),
            hp(w::argument_handle(argv[6])), hj(w::argument_handle(argv[7])),
            hb(w::argument_handle(argv[8]));
        for (auto which : {STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE}) {
            const auto h = GetStdHandle(which);
            if (h && h != INVALID_HANDLE_VALUE)
                invalid("fat_tree_controller_standard_handle");
        }
        w::Security security;
        w::WorkerBudget aggregate(security, false);
        BOOL member = FALSE;
        if (!IsProcessInJob(GetCurrentProcess(), hb.value, &member) || !member)
            invalid("fat_tree_controller_aggregate");
        job_check(hj.value, true);
        w::Image image;
        View input(hi.value, FILE_MAP_READ, sizeof(Input)),
            output(ho.value, FILE_MAP_WRITE, sizeof(Output));
        const auto *in = static_cast<const Input *>(input.value);
        if (!in->length || in->length > input_bytes)
            invalid("fat_tree_controller_input_budget");
        const auto request =
            json::parse(std::string(in->bytes, in->length), fat_tree_review_limits());
        keys(request, {"schema", "review", "grant", "fixture", "host_id", "code_sha256"});
        if (text(request, "schema") != "org.disked.fat-tree-controller-input-prototype/1" ||
            text(request, "host_id") != security.host_id ||
            text(request, "code_sha256") != image.digest)
            invalid("fat_tree_controller_input_binding");
        const auto review = validate_fat_tree_review(field(request, "review"));
        const auto grant = grant_from(field(request, "grant"));
        validate_fat_tree_review_grant(review, grant);
        const auto stall = stall_budget(field(request, "fixture"));
        HANDLE waits[] = {hg.value, ha.value, hp.value};
        if (WaitForMultipleObjects(3, waits, FALSE, 10000) != WAIT_OBJECT_0)
            return 4;
        auto *published = static_cast<Output *>(output.value);
        std::unique_ptr<FatTreeAdmission> owner;
        V last;
        try {
            auto fixture = field(request, "fixture");
            fixture.fields.erase("controller_stall_ms");
            fixture.fields.erase("controller_fault");
            owner = FatTreeAdmission::for_execution(review, grant, fixture);
            owner->launch();
            const auto start = GetTickCount64();
            auto changed = start;
            std::string pulse;
            bool sent = false;
            std::string failure;
            for (;;) {
                last = owner->observe();
                if (boolean(last, "admission_failed"))
                    throw std::runtime_error(text(last, "diagnostic"));
                if (!sent && owner->prepared_review()) {
                    owner->grant(review, grant);
                    sent = true;
                    last = owner->observe();
                    publish(published, reply(request, "admitted", last, {}));
#ifdef DISKED_FAT_TREE_CONTROLLER_TESTING
                    const auto *fault = field(request, "fixture").find("controller_fault");
                    if (fault && fault->text == "exit_after_admitted")
                        return 6;
#endif
                    changed = GetTickCount64();
                }
                if (exited(last))
                    break;
                const auto now = GetTickCount64();
                const auto current = text(field(last, "worker"), "progress_pulse");
                if (current != pulse) {
                    pulse = current;
                    changed = now;
                }
                if ((!sent && now - start >= 10000) ||
                    (sent && (now - changed >= stall || now - start >= 3600000))) {
                    failure = "fat_tree_controller_budget_reached";
                    owner->cancel();
                    last = owner->retire();
                    break;
                }
                Sleep(10);
            }
            if (!sent || !exited(last) || !failure.empty())
                publish(published,
                        reply(request, "unresolved", last,
                              failure.empty() ? "fat_tree_controller_worker_unresolved" : failure));
            else
                publish(published, reply(request, "finished", last, {}));
            // An unavailable owned exit is never replaced. Keep this process and
            // its dependency owner alive until the existing worker actually exits.
            while (!quiescent(last)) {
                Sleep(100);
                last = owner->observe();
            }
            return 0;
        } catch (const std::exception &e) {
            const std::string diagnostic = e.what();
            if (owner) {
                try {
                    owner->cancel();
                    last = owner->retire();
                } catch (...) {
                }
            }
            const auto *effects = last.find("store_effects_possible");
            publish(published,
                    reply(request,
                          effects && effects->kind == V::Kind::boolean && effects->boolean
                              ? "unresolved"
                              : "refused",
                          last, diagnostic));
            if (owner)
                while (!quiescent(last)) {
                    Sleep(100);
                    last = owner->observe();
                }
            return 5;
        }
    } catch (const std::exception &) {
        return 3;
    }
}
} // namespace nt_inventory
} // namespace disked
