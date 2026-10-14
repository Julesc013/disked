#include "platform/windows/worker_files.h"
#include "platform/windows/memory_budget.h"
#include <iostream>
#include <memory>
using namespace disked::worker_files;
using V = disked::json::Value;
struct Attributes {
    std::vector<unsigned char> bytes;
    LPPROC_THREAD_ATTRIBUTE_LIST value = nullptr;
    Attributes(std::vector<HANDLE> &handles, std::vector<HANDLE> &jobs, bool h, bool j) {
        SIZE_T count = 0;
        const DWORD attributes = static_cast<DWORD>(h) + static_cast<DWORD>(j);
        InitializeProcThreadAttributeList(nullptr, attributes, 0, &count);
        bytes.resize(count); value = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(bytes.data());
        if (!InitializeProcThreadAttributeList(value, attributes, 0, &count)) fail("probe_initialize");
        if (h && !UpdateProcThreadAttribute(value, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            handles.data(), handles.size() * sizeof(HANDLE), nullptr, nullptr)) fail("probe_handles");
        if (j && !UpdateProcThreadAttribute(value, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST,
            jobs.data(), jobs.size() * sizeof(HANDLE), nullptr, nullptr)) fail("probe_jobs");
    }
    ~Attributes() { if (value) DeleteProcThreadAttributeList(value); }
};
int wmain(int argc, wchar_t **argv) {
    if (argc < 2 || argc > 4) return 2;
    try {
        const std::wstring image = disked::local_file::path_for(narrow(argv[1]));
        disked::WindowsMemoryBudget memory;
        if (!memory.ready()) {
            std::cout << disked::json::dump(V::object().put("memory_error", V::string(memory.error()))
                .put("platform_code", V::string(std::to_string(memory.platform_error())))) << '\n';
            return 1;
        }
        Handle pin(CreateFileW(image.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
            OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (!pin.valid()) fail("probe_image_pin");
        disked::local_file::ordinary(pin.value, false);
        Directory directory(narrow(image.substr(0, image.find_last_of(L'\\'))));
        std::vector<disked::local_file::Handle> source_parents;
        disked::local_file::Handle source_file;
        if (argc >= 3) {
            const auto source = disked::local_file::path_for(narrow(argv[2]));
            source_parents = disked::local_file::pin_parents(source);
            source_file = disked::local_file::Handle(CreateFileW(source.c_str(), GENERIC_READ, FILE_SHARE_READ,
                nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            if (source_file.value == INVALID_HANDLE_VALUE) fail("probe_source");
            disked::local_file::ordinary(source_file.value, false);
        }
        Security security;
        WorkerBudget aggregate(security, true);
        auto rows = V::array();
        for (unsigned int mode = 0; mode != 4; ++mode) {
            auto sa = security.attributes;
            Handle leaf(CreateJobObjectW(&sa, nullptr));
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            limits.BasicLimitInformation.ActiveProcessLimit = 1;
            limits.ProcessMemoryLimit = 128 * 1024 * 1024;
            if (!leaf.valid() || !SetInformationJobObject(leaf.value, JobObjectExtendedLimitInformation,
                &limits, sizeof(limits))) fail("probe_leaf_job");
            Handle input(CreateFileMappingW(INVALID_HANDLE_VALUE, &sa, PAGE_READWRITE, 0, 278528, nullptr));
            Handle output(CreateFileMappingW(INVALID_HANDLE_VALUE, &sa, PAGE_READWRITE, 0, 786432 + 76, nullptr));
            Handle payload(CreateFileMappingW(INVALID_HANDLE_VALUE, &sa, PAGE_READWRITE, 0, 8 * 1024 * 1024, nullptr));
            Handle cancel(CreateEventW(&sa, TRUE, FALSE, nullptr));
            Handle admitted(CreateEventW(&sa, TRUE, FALSE, nullptr));
            Handle gate(CreateEventW(&sa, TRUE, FALSE, nullptr));
            if (!input.valid() || !output.valid() || !payload.valid() || !cancel.valid() ||
                !admitted.valid() || !gate.valid()) fail("probe_channels");
            auto ci = inherited(input.value, FILE_MAP_READ), co = inherited(output.value, FILE_MAP_WRITE),
                 cc = inherited(cancel.value, SYNCHRONIZE), ca = inherited(admitted.value, EVENT_MODIFY_STATE),
                 cg = inherited(gate.value, SYNCHRONIZE), cp = inherited(payload.value, FILE_MAP_WRITE);
            std::vector<HANDLE> handles = {ci.value, co.value, cc.value, ca.value, cg.value, cp.value},
                                jobs = {aggregate.job.value, leaf.value};
            const bool h = (mode & 1) != 0, j = (mode & 2) != 0;
            std::unique_ptr<Attributes> attributes;
            if (mode) attributes.reset(new Attributes(handles, jobs, h, j));
            STARTUPINFOEXW startup{};
            startup.StartupInfo.cb = mode ? sizeof(startup) : sizeof(STARTUPINFOW);
            startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
            startup.StartupInfo.hStdInput = INVALID_HANDLE_VALUE;
            startup.StartupInfo.hStdOutput = INVALID_HANDLE_VALUE;
            startup.StartupInfo.hStdError = INVALID_HANDLE_VALUE;
            startup.lpAttributeList = attributes ? attributes->value : nullptr;
            // The zero-initialized input section is intentionally invalid. A
            // successfully created compiled reader exits before source access.
            std::wstring command = L"\"" + image + L"\" __disked_fat_reader_worker";
            for (auto handle : handles) command += L" " + std::to_wstring(reinterpret_cast<std::uintptr_t>(handle));
            PROCESS_INFORMATION process{};
            directory.check();
            SetLastError(0);
            const auto created = CreateProcessW(image.c_str(), &command[0], nullptr, nullptr, TRUE,
                DETACHED_PROCESS | (mode ? EXTENDED_STARTUPINFO_PRESENT : 0), nullptr,
                directory.path.c_str(), &startup.StartupInfo, &process);
            const auto error = created ? 0 : GetLastError();
            auto row = V::object().put("handles", V::boolean_value(h)).put("jobs", V::boolean_value(j))
                .put("created", V::boolean_value(created != FALSE))
                .put("platform_code", V::string(std::to_string(error)));
            if (created) {
                Handle owned(process.hProcess), thread(process.hThread);
                auto observed = WaitForSingleObject(owned.value, 5000);
                if (observed == WAIT_TIMEOUT) {
                    // This probe owns a static help-only child; no storage service is called.
                    if (!TerminateProcess(owned.value, 99)) fail("probe_child_cleanup");
                    observed = WaitForSingleObject(owned.value, 2000);
                }
                if (observed != WAIT_OBJECT_0) fail("probe_child_exit_unresolved");
                DWORD code = 0;
                if (!GetExitCodeProcess(owned.value, &code)) fail("probe_child_exit_code");
                row.put("exit_code", V::string(std::to_string(code)));
            }
            rows.items.push_back(std::move(row));
        }
        std::cout << disked::json::dump(V::object().put("memory_private", V::boolean_value(memory.uses_private_job()))
            .put("cases", std::move(rows))) << std::endl;
        if (argc == 4) {
            Handle entered(OpenEventW(EVENT_MODIFY_STATE, FALSE, (std::wstring(argv[3]) + L".entered").c_str()));
            Handle release(OpenEventW(SYNCHRONIZE, FALSE, (std::wstring(argv[3]) + L".release").c_str()));
            if (!entered.valid() || !release.valid() || !SetEvent(entered.value)) fail("probe_gate");
            if (WaitForSingleObject(release.value, 15000) != WAIT_OBJECT_0) fail("probe_gate_wait");
        }
        return 0;
    } catch (const Failure &error) {
        std::cout << disked::json::dump(V::object().put("error", V::string(error.what()))
            .put("platform_code", V::string(std::to_string(error.platform)))) << '\n';
        return 1;
    }
}
