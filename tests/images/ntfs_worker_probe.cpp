#include "platform/windows/storage/ntfs_worker.h"
#include "platform/windows/memory_budget.h"
#include "platform/windows/worker_files.h"
#include "providers/image/local_file.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <iostream>

namespace {
using V = disked::json::Value;
namespace f = disked::local_file;
namespace n = disked::nt_inventory;
const V &get(const V &v, const char *key) {
    const auto *p = v.find(key);
    if (!p)
        throw std::invalid_argument("ntfs_probe_shape");
    return *p;
}
std::string text(const V &v, const char *key) {
    const auto &p = get(v, key);
    if (p.kind != V::Kind::string)
        throw std::invalid_argument("ntfs_probe_shape");
    return p.text;
}
std::uint64_t integer(const V &v, const char *key) {
    const auto s = text(v, key);
    if (!disked::json::decimal_u64(s))
        throw std::invalid_argument("ntfs_probe_integer");
    return std::stoull(s);
}
V security_profile() {
    namespace w = disked::worker_files;
    w::Security security;
    const auto get_dacl=w::symbol<decltype(&GetSecurityDescriptorDacl)>(security.module,"GetSecurityDescriptorDacl");
    const auto get_control=w::symbol<decltype(&GetSecurityDescriptorControl)>(security.module,"GetSecurityDescriptorControl");
    const auto get_ace=w::symbol<decltype(&GetAce)>(security.module,"GetAce");
    const auto sid_string=w::symbol<decltype(&ConvertSidToStringSidW)>(security.module,"ConvertSidToStringSidW");
    const auto token_info=w::symbol<decltype(&GetTokenInformation)>(security.module,"GetTokenInformation");
    const auto token_open=w::symbol<decltype(&OpenProcessToken)>(security.module,"OpenProcessToken");
    HANDLE raw=nullptr;if(!token_open(GetCurrentProcess(),TOKEN_QUERY,&raw))w::fail("security_probe_token");
    w::Handle token(raw);DWORD size=0,container=0;
    if(!token_info(token.value,TokenIsAppContainer,&container,sizeof(container),&size))w::fail("security_probe_token");
    auto observe=[&](const SECURITY_ATTRIBUTES& attributes) {
        BOOL present=FALSE,defaulted=FALSE;PACL acl=nullptr;SECURITY_DESCRIPTOR_CONTROL control=0;DWORD revision=0;
        if(!get_dacl(attributes.lpSecurityDescriptor,&present,&acl,&defaulted) || !present || !acl || acl->AceCount>2 ||
           !get_control(attributes.lpSecurityDescriptor,&control,&revision))w::fail("security_probe_descriptor");
        auto aces=V::array();
        for(DWORD i=0;i<acl->AceCount;++i) {
            void* address=nullptr;if(!get_ace(acl,i,&address))w::fail("security_probe_ace");
            const auto* ace=static_cast<const ACCESS_ALLOWED_ACE*>(address);
            if(ace->Header.AceType!=ACCESS_ALLOWED_ACE_TYPE)throw std::runtime_error("security_probe_ace");
            LPWSTR sid=nullptr;
            if(!sid_string(const_cast<DWORD*>(&ace->SidStart),&sid))w::fail("security_probe_sid");
            const auto text=w::narrow(sid);LocalFree(sid);
            aces.items.push_back(V::object().put("sid",V::string(text)).put("mask",V::string(std::to_string(ace->Mask)))
                .put("flags",V::string(std::to_string(ace->Header.AceFlags))));
        }
        const auto name=w::wide("Local\\DiskEd.Security.Probe."+security.identity(""));
        auto create=attributes;SetLastError(ERROR_SUCCESS);
        w::Handle job(CreateJobObjectW(&create,name.c_str()));const auto created_error=GetLastError();
        if(!job.valid() || created_error==ERROR_ALREADY_EXISTS)w::fail("security_probe_job");
        SetLastError(ERROR_SUCCESS);w::Handle opened(OpenJobObjectW(JOB_OBJECT_QUERY,FALSE,name.c_str()));
        const auto query_error=opened.valid()?0:GetLastError();
        return V::object().put("protected",V::boolean_value((control&SE_DACL_PROTECTED)!=0))
            .put("aces",std::move(aces)).put("query_opened",V::boolean_value(opened.valid()))
            .put("query_error",V::string(std::to_string(query_error)));
    };
    return V::object().put("appcontainer",V::boolean_value(container!=0))
        .put("record",observe(security.attributes)).put("lease",observe(security.lease_attributes));
}
V metadata(const std::string &input) {
    const auto path = f::path_for(input);
    auto parents = f::pin_parents(path);
    const auto generation = f::parent_generations(parents);
    f::Handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                               FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        throw f::Error("ntfs_probe_open", GetLastError());
    f::ordinary(file.value, false);
    f::bind_path(file.value, path);
    f::check_parents(path, parents, generation);
    return f::metadata(file.value).value;
}
V exercise(const V &input) {
    if(const auto* selected=input.find("security_probe")) {
        if(input.fields.size()!=1 || selected->kind!=V::Kind::boolean || !selected->boolean)
            throw std::invalid_argument("security_probe_shape");
        return security_profile();
    }
    disked::NtfsSnapshotInput request;
    request.capture_epoch = input.find("capture_epoch") ? integer(input, "capture_epoch") : 1;
    request.path = text(input, "path");
    if (const auto *selected = input.find("profile")) {
        if (selected->kind != V::Kind::string)
            throw std::invalid_argument("ntfs_probe_profile");
        if (selected->text == "3.0")
            request.profile = disked::NtfsFileProfile::Version30;
        else if (selected->text == "3.1")
            request.profile = disked::NtfsFileProfile::Version31;
        else if (selected->text != "auto")
            throw std::invalid_argument("ntfs_probe_profile");
    }
    request.expected_source =
        input.find("expected_source") ? get(input, "expected_source") : metadata(request.path);
    request.volume_offset = integer(input, "offset");
    request.volume_bytes = integer(input, "length");
    const auto *directory = input.find("directory");
    if (directory) {
        if (directory->kind != V::Kind::object)
            throw std::invalid_argument("ntfs_probe_directory");
        request.kind = disked::NtfsSnapshotKind::Directory;
        if (directory->find("reference"))
            request.directory_reference = integer(*directory, "reference");
    }
    const auto *membership = input.find("membership");
    if (membership) {
        if (membership->kind != V::Kind::object)
            throw std::invalid_argument("ntfs_probe_membership");
        request.kind = disked::NtfsSnapshotKind::Membership;
    }
    if (const auto *upcase = input.find("upcase")) {
        if (upcase->kind != V::Kind::boolean || !upcase->boolean || directory || membership)
            throw std::invalid_argument("ntfs_probe_upcase");
        request.kind = disked::NtfsSnapshotKind::Upcase;
    }
    if (const auto *name_order = input.find("name_order")) {
        if (name_order->kind != V::Kind::boolean || !name_order->boolean || !directory ||
            membership || input.find("upcase"))
            throw std::invalid_argument("ntfs_probe_name_order");
        request.kind = disked::NtfsSnapshotKind::NameOrder;
    }
    if (input.find("nonmember_target_limit")) {
        const auto cap = integer(input, "nonmember_target_limit");
        request.target_limit = cap > 256 ? 257 : static_cast<std::size_t>(cap);
    }
    if (input.find("invalid_kind"))
        request.kind = static_cast<disked::NtfsSnapshotKind>(99);
    if (input.find("bootstrap_directory_controls")) {
        request.kind = disked::NtfsSnapshotKind::Bootstrap;
        request.directory_reference = 1;
    }
    auto value = disked::ntfs_snapshot_input_value(request);
    if (membership)
        if (const auto *cap = membership->find("targets"))
            value.put("target_limit", *cap);
    if (const auto *limits = input.find("limits"))
        for (const auto &p : limits->fields)
            value.fields.at("limits").put(p.first, p.second);
    if (directory)
        if (const auto *limits = directory->find("limits"))
            for (const auto &p : limits->fields)
                value.fields.at("directory_limits").put(p.first, p.second);
    if (const auto *fixture = input.find("fixture"))
        value.put("fixture", *fixture);
    for (const auto key : {"startup_fault", "reply_fault"})
        if (const auto *fixture = input.find("fixture"))
            if (const auto *p = fixture->find(key))
                value.put(key, *p);
    auto header = V::object()
                      .put("capture_epoch", V::string(std::to_string(request.capture_epoch)))
                      .put("policy", V::object())
                      .put("provider_input", std::move(value));
    if (const auto *replacement = input.find("replace_input"))
        header.put("provider_input", *replacement);
    request = disked::ntfs_snapshot_input_from(header);
    const auto mode = input.find("mode") ? text(input, "mode") : "worker";
    if (mode == "decode_input")
        return V::object().put("input", disked::ntfs_snapshot_input_value(request));
    if (mode == "verify")
        return V::object().put("verified",
                               disked::verify_ntfs_snapshot_frame(get(input, "replace"), request));
    if (mode == "frame") {
        auto captured = disked::read_ntfs_snapshot_frame(request);
        return V::object()
            .put("frame", captured)
            .put("verified", disked::verify_ntfs_snapshot_frame(captured, request));
    }
    const auto prepare_begin = GetTickCount64();
    auto worker = n::NtfsWorker::prepare(request);
    const auto prepare_ms = GetTickCount64() - prepare_begin;
    if (input.find("mutate_after_prepare")) {
        request.path = "invalid-mutated-path";
        request.kind = static_cast<disked::NtfsSnapshotKind>(99);
        request.directory_reference = 1;
        request.directory_limits.entries = 0;
        request.target_limit = 0;
        request.expected_source = V{};
        request.limits.read_requests = 0;
        request.fixture = V::object().put("worker_fault", V::string("hang"));
    }
    if (mode == "construction")
        return V::object().put("never_launched", V::boolean_value(worker->never_launched()));
    auto startup = V::object()
                       .put("prepare_ms", V::string(std::to_string(prepare_ms)))
                       .put("wait_entered_ran", V::boolean_value(false));
    auto out = V::object();
    const auto launch_begin = GetTickCount64();
    try {
        worker->launch();
    } catch (const std::exception &error) {
        startup.put("launch_ms", V::string(std::to_string(GetTickCount64() - launch_begin)));
        out.put("startup", std::move(startup))
            .put("startup_error", V::string(error.what()))
            .put("never_launched", V::boolean_value(worker->never_launched()))
            .put("before", worker->observe());
        if (!worker->never_launched())
            out.put("retirement", worker->retire());
        return out;
    }
    startup.put("launch_ms", V::string(std::to_string(GetTickCount64() - launch_begin)));
    const auto entered_begin = GetTickCount64();
    const bool entered = worker->wait_entered(1000);
    startup.put("wait_entered_ran", V::boolean_value(true))
        .put("wait_entered", V::boolean_value(entered))
        .put("wait_entered_budget_ms", V::string("1000"))
        .put("wait_entered_ms", V::string(std::to_string(GetTickCount64() - entered_begin)));
    out.put("startup", std::move(startup));
    if (!entered) {
        const auto before = worker->observe();
        const auto retirement = worker->retire();
        return out.put("before", before)
            .put("has_snapshot", V::boolean_value(false))
            .put("retirement", retirement);
    }
    if (input.find("cancel"))
        worker->cancel();
    {
        const auto current = worker->observe();
        const auto &identity = get(current, "worker");
        const auto pid = integer(identity, "pid");
        f::Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE,
                                      static_cast<DWORD>(pid)));
        FILETIME created{}, exited{}, kernel{}, user{};
        BOOL in_job = FALSE;
        if (process.value == INVALID_HANDLE_VALUE || !process.value ||
            !GetProcessTimes(process.value, &created, &exited, &kernel, &user) ||
            !IsProcessInJob(process.value, nullptr, &in_job))
            throw std::runtime_error("ntfs_probe_process_identity");
        out.put("independent_process",
                V::object()
                    .put("pid", V::string(std::to_string(GetProcessId(process.value))))
                    .put("created", V::string(std::to_string(
                                        (static_cast<std::uint64_t>(created.dwHighDateTime) << 32) |
                                        created.dwLowDateTime)))
                    .put("in_job", V::boolean_value(in_job != FALSE)));
    }
    worker->release();
    if (mode == "publication-live") {
        V before;
        const auto end = GetTickCount64() + 400;
        do {
            before = worker->observe(10);
            const auto *diagnostic = before.find("diagnostic");
            if ((diagnostic && diagnostic->kind == V::Kind::string &&
                 diagnostic->text == "ntfs_worker_exit_pending") ||
                text(get(before, "worker"), "observation") == "exited")
                break;
        } while (GetTickCount64() < end);
        const auto available = bool(worker->snapshot());
        return out.put("before", before)
            .put("has_snapshot", V::boolean_value(available))
            .put("retirement", worker->retire());
    }
    if (mode == "pending") {
        auto before = worker->observe(50);
        const bool has_snapshot = bool(worker->snapshot());
        const auto retirement = worker->retire();
        return out.put("before", std::move(before))
            .put("has_snapshot", V::boolean_value(has_snapshot))
            .put("retirement", retirement);
    }
    if (mode == "retire-zero") {
        const auto before = worker->observe(50);
        const auto zero = worker->retire(0);
        return out.put("before", before)
            .put("zero_retirement", zero)
            .put("retirement", worker->retire());
    }
    auto samples = V::array();
    const auto deadline = GetTickCount64() + 5000;
    V last;
    do {
        last = worker->observe(10);
        samples.items.push_back(last);
        if (text(get(last, "worker"), "observation") == "exited" ||
            text(last, "status") == "completed")
            break;
    } while (GetTickCount64() < deadline);
    const auto snapshot = worker->snapshot(true);
    const auto retained =
        snapshot ? disked::json::dump(snapshot->result(), disked::ntfs_snapshot_json_limits())
                 : std::string{};
    out.put("samples", std::move(samples))
        .put("before", last)
        .put("has_snapshot", V::boolean_value(bool(snapshot)));
    if (snapshot)
        out.put("snapshot", snapshot->result())
            .put("context", snapshot->context())
            .put("frame", snapshot->frame());
    out.put("retirement", worker->retire());
    worker.reset();
    out.put("retained_unchanged",
            V::boolean_value(snapshot &&
                             retained == disked::json::dump(snapshot->result(),
                                                            disked::ntfs_snapshot_json_limits())));
    return out;
}
} // namespace
int wmain(int argc, wchar_t **argv) {
    if (argc > 1 && std::wcscmp(argv[1], L"__disked_ntfs_reader_worker") == 0)
        return n::ntfs_worker_role(argc, argv);
    if (argc != 1 || _setmode(_fileno(stdin), _O_BINARY) < 0 ||
        _setmode(_fileno(stdout), _O_BINARY) < 0)
        return 2;
    try {
        disked::WindowsMemoryBudget budget;
        if (!budget.ready())
            throw std::runtime_error(budget.error());
        auto limits = disked::ntfs_snapshot_json_limits();
        limits.bytes = 16777216;
        limits.string_bytes = 12582912;
        std::string line;
        while (std::getline(std::cin, line)) {
            V out;
            try {
                out = exercise(disked::json::parse(line, limits));
            } catch (const std::exception &error) {
                out = V::object().put("error", V::string(error.what()));
            }
            std::cout << disked::json::dump(out, limits) << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
