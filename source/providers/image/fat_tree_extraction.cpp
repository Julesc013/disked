#include "fat_tree_extraction.h"
#include "local_file.h"
#include "portable/hash/sha256.h"
#include <winternl.h>
#include <algorithm>
#include <cstring>
#include <map>
#include <set>

namespace disked {
namespace {
using V = json::Value;
using Bytes = std::vector<unsigned char>;
namespace f = local_file;
[[noreturn]] void fail(const char *code, DWORD platform = 0) {
    throw FatTreeExtractionError(code, platform);
}
V exact(std::uint64_t value) {
    return V::string(std::to_string(value));
}
const V &field(const V &value, const char *key) {
    const auto *p = value.find(key);
    if (!p)
        fail("fat_tree_extract_shape");
    return *p;
}
std::uint64_t integer(const V &value) {
    if (value.kind != V::Kind::string || !json::decimal_u64(value.text))
        fail("fat_tree_extract_integer");
    return std::stoull(value.text);
}
json::Limits limits() {
    json::Limits l;
    l.bytes = 262144;
    l.depth = 32;
    l.values = 65536;
    l.string_bytes = 32768;
    return l;
}
std::string encode(const V &value) {
    return json::dump(value, limits());
}
std::string hash(const unsigned char *data, std::size_t size) {
    unsigned char digest[32];
    sha256(data, size, digest);
    const char digits[] = "0123456789abcdef";
    std::string out = "sha256:";
    for (const auto byte : digest) {
        out += digits[byte >> 4];
        out += digits[byte & 15];
    }
    return out;
}
std::string hash(const std::string &text) {
    return hash(reinterpret_cast<const unsigned char *>(text.data()), text.size());
}
std::wstring wide_units(const V &value) {
    if (value.kind != V::Kind::array || value.items.empty() || value.items.size() > 255)
        fail("fat_tree_extract_name");
    std::wstring out;
    for (const auto &unit : value.items) {
        const auto n = integer(unit);
        if (n > UINT16_MAX)
            fail("fat_tree_extract_name");
        out += static_cast<wchar_t>(n);
    }
    return out;
}
Bytes unhex(const std::string &text) {
    if (text.size() % 2 || text.size() > 131072 ||
        text.find_first_not_of("0123456789abcdef") != text.npos)
        fail("fat_tree_extract_data");
    Bytes out;
    out.reserve(text.size() / 2);
    auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
    for (std::size_t i = 0; i < text.size(); i += 2)
        out.push_back(static_cast<unsigned char>(digit(text[i]) * 16 + digit(text[i + 1])));
    return out;
}
bool exists(const std::wstring &path) {
    if (GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES)
        return true;
    const auto code = GetLastError();
    if (code == ERROR_FILE_NOT_FOUND || code == ERROR_PATH_NOT_FOUND)
        return false;
    fail("fat_tree_extract_absence", code);
}
bool same_name(const std::wstring &a, const std::wstring &b) {
    const auto compared = CompareStringOrdinal(a.data(), static_cast<int>(a.size()), b.data(),
                                               static_cast<int>(b.size()), TRUE);
    if (!compared)
        fail("fat_tree_extract_name_compare", GetLastError());
    return compared == CSTR_EQUAL;
}
struct NameLess {
    bool operator()(const std::wstring &a, const std::wstring &b) const {
        const auto compared = CompareStringOrdinal(a.data(), static_cast<int>(a.size()), b.data(),
                                                   static_cast<int>(b.size()), TRUE);
        if (!compared)
            fail("fat_tree_extract_name_compare", GetLastError());
        return compared == CSTR_LESS_THAN;
    }
};
struct Path {
    std::wstring value, leaf;
    std::vector<f::Handle> parents;
    V generations;
    explicit Path(const std::string &input)
        : value(f::path_for(input)), parents(f::pin_parents(value)),
          generations(f::parent_generations(parents)) {
        leaf = value.substr(value.rfind(L'\\') + 1);
        if (leaf.empty() || value.size() <= 3)
            fail("fat_tree_extract_path");
    }
    void check() const {
        f::check_parents(value, parents, generations);
    }
    V location() const {
        return V::object()
            .put("parent", generations.items.back())
            .put("leaf", V::string(f::utf8(leaf)))
            .put("absence_required", V::boolean_value(true));
    }
};
f::Handle open_read(const Path &path) {
    f::Handle out(CreateFileW(path.value.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                              OPEN_EXISTING,
                              FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, nullptr));
    if (out.value == INVALID_HANDLE_VALUE)
        fail("fat_tree_extract_open", GetLastError());
    f::ordinary(out.value, false);
    f::bind_path(out.value, path.value);
    return out;
}
void seek(HANDLE handle, std::uint64_t offset) {
    if (offset > static_cast<std::uint64_t>(MAXLONGLONG))
        fail("fat_tree_extract_offset");
    LARGE_INTEGER at{};
    at.QuadPart = static_cast<LONGLONG>(offset);
    if (!SetFilePointerEx(handle, at, nullptr, FILE_BEGIN))
        fail("fat_tree_extract_seek", GetLastError());
}
Bytes read(HANDLE handle, std::uint64_t offset, std::size_t count) {
    if (count > 65536)
        fail("fat_tree_extract_read_budget");
    seek(handle, offset);
    Bytes bytes(count);
    DWORD got = 0;
    if (count && !ReadFile(handle, bytes.data(), static_cast<DWORD>(count), &got, nullptr))
        fail("fat_tree_extract_read", GetLastError());
    if (got != count)
        fail("fat_tree_extract_short_read");
    return bytes;
}
void write(HANDLE handle, const unsigned char *bytes, std::size_t count) {
    if (count > 262144)
        fail("fat_tree_extract_write_budget");
    DWORD got = 0;
    if (count && !WriteFile(handle, bytes, static_cast<DWORD>(count), &got, nullptr))
        fail("fat_tree_extract_write", GetLastError());
    if (got != count)
        fail("fat_tree_extract_short_write");
}
void flush(HANDLE handle) {
    if (!FlushFileBuffers(handle))
        fail("fat_tree_extract_flush", GetLastError());
}
V identity(HANDLE handle, bool directory) {
    const auto value = f::generation(handle, directory);
    return V::object()
        .put("volume_id", field(value, "volume_id"))
        .put("file_id", field(value, "file_id"));
}
struct Owned {
    f::Handle handle;
    std::wstring path;
    V id;
    bool directory;
    Owned(f::Handle value, std::wstring selected, bool dir)
        : handle(std::move(value)), path(std::move(selected)), id(identity(handle.value, dir)),
          directory(dir) {
        check();
    }
    void check() const {
        f::ordinary(handle.value, directory);
        f::bind_path(handle.value, path);
        if (encode(identity(handle.value, directory)) != encode(id))
            fail("fat_tree_extract_output_changed");
    }
};
f::Handle create_child(HANDLE parent, const std::wstring &component, bool directory) {
    if (component.empty() || component.size() > 255 ||
        component.find_first_of(L"\\/:") != component.npos || component == L"." ||
        component == L"..")
        fail("fat_tree_extract_component");
    f::ordinary(parent, true);
    using Create = decltype(&NtCreateFile);
    const auto module = GetModuleHandleW(L"ntdll.dll");
    auto address = module ? GetProcAddress(module, "NtCreateFile") : nullptr;
    if (!address)
        fail("fat_tree_extract_create_unavailable", GetLastError());
    Create create = nullptr;
    static_assert(sizeof(create) == sizeof(address), "Selected Windows ABI function pointer size");
    std::memcpy(&create, &address, sizeof(create));
    UNICODE_STRING name{};
    name.Length = static_cast<USHORT>(component.size() * sizeof(wchar_t));
    name.MaximumLength = name.Length;
    name.Buffer = const_cast<wchar_t *>(component.data());
    OBJECT_ATTRIBUTES attributes{};
    attributes.Length = sizeof(attributes);
    attributes.RootDirectory = parent;
    attributes.ObjectName = &name;
    attributes.Attributes = OBJ_CASE_INSENSITIVE;
    IO_STATUS_BLOCK io{};
    HANDLE raw = INVALID_HANDLE_VALUE;
    const ACCESS_MASK access = directory
                                   ? FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES |
                                         FILE_WRITE_ATTRIBUTES | SYNCHRONIZE
                                   : FILE_GENERIC_READ | FILE_GENERIC_WRITE;
    const auto status = create(&raw, access, &attributes, &io, nullptr, FILE_ATTRIBUTE_NORMAL,
                               directory ? FILE_SHARE_READ : 0, FILE_CREATE,
                               (directory ? FILE_DIRECTORY_FILE : FILE_NON_DIRECTORY_FILE) |
                                   FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                               nullptr, 0);
    f::Handle out(raw);
    if (status < 0)
        throw FatTreeExtractionError("fat_tree_extract_create", static_cast<DWORD>(status),
                                     "ntstatus");
    if (io.Information != FILE_CREATED || raw == INVALID_HANDLE_VALUE)
        fail("fat_tree_extract_create_identity");
    return out;
}
std::wstring executable_path() {
    wchar_t path[241];
    const auto count = GetModuleFileNameW(nullptr, path, 241);
    if (!count || count >= 241)
        fail("fat_tree_extract_code_path", GetLastError());
    return std::wstring(path, count);
}
FILE_BASIC_INFO basic(HANDLE handle) {
    FILE_BASIC_INFO value{};
    if (!GetFileInformationByHandleEx(handle, FileBasicInfo, &value, sizeof(value)))
        fail("fat_tree_extract_basic_metadata", GetLastError());
    return value;
}
V time_result(const V &candidate, LONGLONG observed) {
    if (observed < 0)
        fail("fat_tree_extract_time_readback");
    auto result = V::object()
                      .put("candidate", candidate)
                      .put("observed_filetime", exact(static_cast<std::uint64_t>(observed)));
    if (field(candidate, "status").text != "candidate")
        return result.put("status", V::string("unapplied"));
    return result.put("status", V::string(integer(field(candidate, "filetime_candidate")) ==
                                                  static_cast<std::uint64_t>(observed)
                                              ? "applied_verified"
                                              : "application_mismatch"));
}
V apply_metadata(const Owned &owned, const V &mapping) {
    owned.check();
    FILE_BASIC_INFO attributes{};
    const auto flags = static_cast<DWORD>(integer(field(mapping, "native_attributes_candidate")));
    attributes.FileAttributes = flags ? flags : FILE_ATTRIBUTE_NORMAL;
    if (!SetFileInformationByHandle(owned.handle.value, FileBasicInfo, &attributes,
                                    sizeof(attributes)))
        fail("fat_tree_extract_attributes", GetLastError());
    FILETIME times[3]{};
    const FILETIME *selected[3]{};
    const char *names[] = {"creation", "access", "write"};
    for (std::size_t i = 0; i < 3; ++i) {
        const auto &value = field(mapping, names[i]);
        if (field(value, "status").text == "candidate") {
            const auto ticks = integer(field(value, "filetime_candidate"));
            times[i].dwLowDateTime = static_cast<DWORD>(ticks);
            times[i].dwHighDateTime = static_cast<DWORD>(ticks >> 32);
            selected[i] = &times[i];
        }
    }
    if (!SetFileTime(owned.handle.value, selected[0], selected[1], selected[2]))
        fail("fat_tree_extract_times", GetLastError());
    owned.check(); // File ID remains stable even when creation time changes.
    const auto observed = basic(owned.handle.value);
    return V::object()
        .put("creation", time_result(field(mapping, "creation"), observed.CreationTime.QuadPart))
        .put("access", time_result(field(mapping, "access"), observed.LastAccessTime.QuadPart))
        .put("write", time_result(field(mapping, "write"), observed.LastWriteTime.QuadPart))
        .put("attributes", V::object()
                               .put("candidate", exact(flags))
                               .put("observed", exact(observed.FileAttributes))
                               .put("status", V::string((observed.FileAttributes & 0x27) == flags
                                                            ? "applied_verified"
                                                            : "application_mismatch")));
}
bool metadata_matches(const V &value) {
    for (const char *name : {"creation", "access", "write", "attributes"})
        if (field(field(value, name), "status").text == "application_mismatch")
            return false;
    return true;
}
bool cancelled_frame(const V &frame) {
    const auto *checks = frame.find("checks");
    if (checks)
        for (const auto &check : checks->items)
            if (field(check, "cancelled").boolean)
                return true;
    return false;
}
} // namespace

struct FatTreeExtraction::Impl {
    FatTreeExtractionRequest request;
    Path source_path, destination_path, ledger_path, code_path;
    f::Handle source, code, ledger;
    V source_metadata, code_metadata, definition, preparation_binding, ledger_identity;
    std::string code_hash, definition_digest, tree_digest;
    std::unique_ptr<FatTreeFile> tree;
    struct Node {
        std::string key, parent, metadata_digest;
        std::wstring name, path;
        std::uint64_t bytes = 0;
        bool directory = false;
    };
    std::vector<Node> nodes;
    std::vector<std::string> page_events;
    std::map<std::string, std::size_t> indices;
    std::map<std::string, std::set<std::wstring, NameLess>> names;
    std::map<std::string, std::unique_ptr<Owned>> directories;
    std::uint64_t total_bytes = 0, metadata_bytes = 0, ledger_bytes = 0, sequence = 0;
    std::uint64_t files_done = 0, verified_bytes = 0, checkpointed_bytes = 0, directories_done = 0;
    std::string previous = "sha256:" + std::string(64, '0');
    FatTreeExtractionHooks hooks;
    bool executed = false, effects_possible = false, completion_flushed = false,
         cancellation_seen = false;
    explicit Impl(const FatTreeExtractionRequest &value)
        : request(value), source_path(value.tree.path), destination_path(value.destination),
          ledger_path(value.ledger), code_path(f::utf8(executable_path())) {
        fat_metadata_policy_value(request.metadata);
        if (!request.entries || request.entries > 65536 || !request.directories ||
            request.directories > 4096 || request.metadata_bytes < 16384 ||
            request.metadata_bytes > 67108864 || !request.pages || request.pages > 65536 ||
            !request.content_bytes || request.content_bytes > 1099511627776ULL ||
            request.ledger_bytes < 1048576 || request.ledger_bytes > 1073741824)
            fail("fat_tree_extract_budget");
        if (same_name(destination_path.value, ledger_path.value))
            fail("fat_tree_extract_alias");
        if (exists(destination_path.value) || exists(ledger_path.value))
            fail("fat_tree_extract_exists");
        for (const auto *path : {&destination_path, &ledger_path}) {
            wchar_t filesystem[32]{};
            if (!GetVolumeInformationByHandleW(path->parents.back().value, nullptr, 0, nullptr,
                                               nullptr, nullptr, filesystem, 32))
                fail("fat_tree_extract_volume_profile", GetLastError());
            if (!same_name(filesystem, L"NTFS"))
                fail("fat_tree_extract_ntfs_required");
        }
        source = open_read(source_path);
        code = open_read(code_path);
        source_metadata = f::metadata(source.value).value;
        code_metadata = f::metadata(code.value).value;
        if (request.tree.expected_source.kind != V::Kind::null &&
            encode(request.tree.expected_source) != encode(source_metadata))
            fail("fat_tree_extract_source_changed");
        request.tree.expected_source = source_metadata;
        request.tree.path = f::utf8(source_path.value);
        const auto code_bytes = f::metadata(code.value).size;
        if (!code_bytes || code_bytes > 8388608)
            fail("fat_tree_extract_code_budget");
        Bytes image;
        image.reserve(static_cast<std::size_t>(code_bytes));
        for (std::uint64_t at = 0; at < code_bytes;) {
            const auto bytes =
                read(code.value, at,
                     static_cast<std::size_t>((std::min)(std::uint64_t(65536), code_bytes - at)));
            image.insert(image.end(), bytes.begin(), bytes.end());
            at += bytes.size();
        }
        code_hash = hash(image.data(), image.size());
        tree.reset(new FatTreeFile(request.tree));
        prepare();
        fresh();
        wchar_t machine[MAX_COMPUTERNAME_LENGTH + 1]{};
        DWORD machine_size = MAX_COMPUTERNAME_LENGTH + 1;
        if (!GetComputerNameW(machine, &machine_size))
            fail("fat_tree_extract_host", GetLastError());
        auto observations =
            V::object()
                .put("source", source_metadata)
                .put("source_parents", source_path.generations)
                .put("destination_tree", destination_path.location())
                .put("destination_parents", destination_path.generations)
                .put("metadata_ledger", ledger_path.location())
                .put("ledger_parents", ledger_path.generations)
                .put("executable", code_metadata)
                .put("executable_sha256", V::string(code_hash))
                .put("executable_parents", code_path.generations)
                .put("provider", V::string("provider.image.fat-tree-extract.prototype/1"))
                .put("host_profile", V::string("windows.nt10.x64.local-ntfs.prototype/1"))
                .put("host_identity",
                     V::string(hash(f::utf8(std::wstring(machine, machine_size)))));
        auto bound = [](V observed, const char *access, V footprint, const char *verification,
                        const std::string &domain) {
            const auto encoded = encode(observed);
            const auto id = "observed:" + hash(encoded);
            auto aliases = V::array();
            aliases.items.push_back(V::string(id));
            const auto *file = observed.find("file");
            if (file)
                aliases.items.push_back(V::string(
                    "file:" + hash(encode(V::object()
                                              .put("volume_id", field(*file, "volume_id"))
                                              .put("file_id", field(*file, "file_id"))))));
            return V::object()
                .put("identity", V::string(id))
                .put("epoch", V::string(hash(encoded)))
                .put("observed", std::move(observed))
                .put("access", V::string(access))
                .put("footprint", std::move(footprint))
                .put("verification", V::string(verification))
                .put("aliases", std::move(aliases))
                .put("failure_domain", V::string(domain));
        };
        const auto source_observation = V::object()
                                            .put("file", source_metadata)
                                            .put("parents", source_path.generations)
                                            .put("path", V::string(f::utf8(source_path.value)));
        const auto code_observation = V::object()
                                          .put("file", code_metadata)
                                          .put("parents", code_path.generations)
                                          .put("path", V::string(f::utf8(code_path.value)))
                                          .put("sha256", V::string(code_hash));
        auto resources =
            V::object()
                .put("source",
                     bound(source_observation, "read",
                           V::object()
                               .put("kind", V::string("byte-range"))
                               .put("start", exact(request.tree.volume_offset))
                               .put("end",
                                    exact(request.tree.volume_offset + request.tree.volume_bytes)),
                           "held-identity-and-region-agreement",
                           "observed-file-volume:" + field(source_metadata, "volume_id").text))
                .put("destination_tree",
                     bound(V::object()
                               .put("location", destination_path.location())
                               .put("parents", destination_path.generations),
                           "create-tree",
                           V::object()
                               .put("kind", V::string("new-descendant-tree"))
                               .put("entries", exact(nodes.size()))
                               .put("content_bytes", exact(total_bytes)),
                           "file-id-and-content-readback",
                           "observed-file-volume:" +
                               field(destination_path.generations.items.back(), "volume_id").text))
                .put("metadata_ledger",
                     bound(V::object()
                               .put("location", ledger_path.location())
                               .put("parents", ledger_path.generations),
                           "create-append",
                           V::object()
                               .put("kind", V::string("bounded-new-file"))
                               .put("bytes", exact(request.ledger_bytes)),
                           "ordered-hash-chain",
                           "observed-file-volume:" +
                               field(ledger_path.generations.items.back(), "volume_id").text))
                .put("executable",
                     bound(code_observation, "read",
                           V::object()
                               .put("kind", V::string("byte-range"))
                               .put("start", exact(0))
                               .put("end", exact(code_bytes)),
                           "identity-and-code-sha256",
                           "observed-file-volume:" + field(code_metadata, "volume_id").text))
                .put("provider",
                     bound(V::object()
                               .put("id", field(observations, "provider"))
                               .put("code_sha256", V::string(code_hash)),
                           "execute-linked",
                           V::object().put("kind", V::string("declared-provider-effects")),
                           "same-linked-generation", "linked-executable-generation"))
                .put("host",
                     bound(V::object()
                               .put("identity", field(observations, "host_identity"))
                               .put("profile", field(observations, "host_profile")),
                           "declared-host-effects",
                           V::object().put("kind",
                                           V::string("ordinary-local-process-and-file-effects")),
                           "selected-host-profile", "observed-local-host"));
        definition =
            V::object()
                .put("schema", V::string("org.disked.fat-tree-extraction-plan-prototype/1"))
                .put("selection", V::object()
                                      .put("kind", V::string("whole-live-tree"))
                                      .put("volume_offset", exact(request.tree.volume_offset))
                                      .put("volume_bytes", exact(request.tree.volume_bytes))
                                      .put("fat_copy", exact(request.tree.fat_copy))
                                      .put("capture_epoch", exact(request.tree.capture_epoch))
                                      .put("preparation_binding", preparation_binding)
                                      .put("tree_digest", V::string(tree_digest))
                                      .put("pages", exact(page_events.size()))
                                      .put("entries", exact(nodes.size()))
                                      .put("content_bytes", exact(total_bytes)))
                .put("prepared_input", fat_tree_input_value(request.tree))
                .put("paths", V::object()
                                  .put("source", V::string(f::utf8(source_path.value)))
                                  .put("destination", V::string(f::utf8(destination_path.value)))
                                  .put("ledger", V::string(f::utf8(ledger_path.value))))
                .put("resources", std::move(resources))
                .put("metadata_policy", fat_metadata_policy_value(request.metadata))
                .put("budgets", V::object()
                                    .put("entries", exact(request.entries))
                                    .put("directories", exact(request.directories))
                                    .put("metadata_bytes", exact(request.metadata_bytes))
                                    .put("pages", exact(request.pages))
                                    .put("content_bytes", exact(request.content_bytes))
                                    .put("ledger_bytes", exact(request.ledger_bytes))
                                    .put("record_bytes", exact(262144))
                                    .put("code_bytes", exact(8388608))
                                    .put("native_path_units", exact(240)))
                .put("effects", V::string("create-only-tree-and-independent-ordered-ledger"))
                .put("scratch_resources", V::array())
                .put("recovery_resources", V::array())
                .put("source_consistency", V::string("held-identity-and-read-agreement-not-atomic"))
                .put("owner_accepted", V::boolean_value(false));
        definition_digest = hash("disked:fat-tree-extraction-plan:1\n" + encode(definition));
    }
    void fresh() const {
        for (const auto *path : {&source_path, &destination_path, &ledger_path, &code_path})
            path->check();
        f::bind_path(source.value, source_path.value);
        f::bind_path(code.value, code_path.value);
        if (encode(f::metadata(source.value).value) != encode(source_metadata) ||
            encode(f::metadata(code.value).value) != encode(code_metadata))
            fail("fat_tree_extract_resource_changed");
        if (ledger.value != INVALID_HANDLE_VALUE) {
            f::ordinary(ledger.value, false);
            f::bind_path(ledger.value, ledger_path.value);
            if (encode(identity(ledger.value, false)) != encode(ledger_identity))
                fail("fat_tree_extract_ledger_changed");
        }
        for (const auto &directory : directories)
            directory.second->check();
    }
    void stop() {
        if (hooks.stop && hooks.stop()) {
            cancellation_seen = true;
            fail("fat_tree_extract_cancelled");
        }
    }
    void boundary(const char *name) const {
        if (hooks.boundary)
            hooks.boundary(name);
    }
    void prepare() {
        std::size_t directory_count = 1;
        while (!tree->finished()) {
            if (page_events.size() == request.pages)
                fail("fat_tree_extract_page_budget");
            const auto frame = tree->next();
            const auto &page = field(frame, "page");
            if (!field(page, "applicable").boolean)
                fail("fat_tree_extract_prepare_source");
            if (page_events.empty())
                preparation_binding = field(page, "binding");
            page_events.push_back(hash(encode(field(page, "events"))));
            tree_digest = hash(tree_digest + ":" + page_events.back());
            for (const auto &record : field(page, "events").items) {
                if (field(record, "type").text != "record")
                    continue;
                const auto kind = integer(field(record, "kind"));
                if ((kind != 3 && kind != 4) || integer(field(record, "dot")))
                    continue;
                if (nodes.size() == request.entries)
                    fail("fat_tree_extract_entry_budget");
                const auto key = field(record, "key").text,
                           parent = field(record, "directory").text;
                const auto mapping =
                    field(tree->metadata_candidates(key, request.metadata), "mapping");
                if (field(mapping, "status").text != "candidate")
                    fail("fat_tree_extract_metadata_refused");
                const auto encoded = encode(mapping);
                if (encoded.size() > request.metadata_bytes - metadata_bytes)
                    fail("fat_tree_extract_metadata_budget");
                metadata_bytes += encoded.size();
                Node node;
                node.key = key;
                node.parent = parent;
                node.directory = kind == 4;
                node.bytes = integer(field(record, "file_bytes"));
                node.metadata_digest = hash(encoded);
                node.name = wide_units(field(field(mapping, "name"), "utf16_units"));
                if (!names[parent].insert(node.name).second)
                    fail("fat_tree_extract_name_collision");
                auto parent_path = destination_path.value;
                if (parent != "root") {
                    const auto found = indices.find(parent);
                    if (found == indices.end() || !nodes[found->second].directory)
                        fail("fat_tree_extract_parent");
                    parent_path = nodes[found->second].path;
                }
                node.path = parent_path + L"\\" + node.name;
                if (node.path.size() > 240)
                    fail("fat_tree_extract_path_budget");
                if (node.directory && ++directory_count > request.directories)
                    fail("fat_tree_extract_directory_budget");
                if (node.bytes > request.content_bytes - total_bytes)
                    fail("fat_tree_extract_content_budget");
                total_bytes += node.bytes;
                if (!indices.emplace(node.key, nodes.size()).second)
                    fail("fat_tree_extract_entry_reused");
                nodes.push_back(std::move(node));
            }
            if (field(page, "status").text == "partial")
                fail("fat_tree_extract_prepare_incomplete");
        }
    }
    void append(const char *kind, V payload) {
        auto record =
            V::object()
                .put("schema", V::string("org.disked.fat-tree-extraction-record-prototype/1"))
                .put("sequence", exact(sequence))
                .put("previous", V::string(previous))
                .put("definition_digest", V::string(definition_digest))
                .put("attempt_id", V::string(hooks.attempt_id))
                .put("kind", V::string(kind))
                .put("payload", std::move(payload));
        const auto text = encode(record) + "\n";
        if (text.size() > request.ledger_bytes - ledger_bytes)
            fail("fat_tree_extract_ledger_budget");
        fresh();
        write(ledger.value, reinterpret_cast<const unsigned char *>(text.data()), text.size());
        flush(ledger.value);
        previous = hash(text);
        ++sequence;
        ledger_bytes += text.size();
        if (std::string(kind) == "checkpoint")
            checkpointed_bytes += integer(field(field(record, "payload"), "bytes"));
        if (std::string(kind) == "file-complete")
            ++files_done;
        if (std::string(kind) == "outcome" &&
            field(field(record, "payload"), "status").text == "complete")
            completion_flushed = true;
        boundary("ledger_flushed");
    }
    V intent(const Node &node, const char *effect) const {
        return V::object()
            .put("key", V::string(node.key))
            .put("parent", V::string(node.parent))
            .put("path", V::string(f::utf8(node.path)))
            .put("effect", V::string(effect));
    }
    void file(const Node &node, const V &mapping) {
        append("intent", intent(node, "create-file"));
        stop();
        fresh();
        auto parent = directories.find(node.parent);
        if (parent == directories.end())
            fail("fat_tree_extract_parent");
        Owned output(create_child(parent->second->handle.value, node.name, false), node.path,
                     false);
        boundary("file_created");
        FILETIME disabled{MAXDWORD, MAXDWORD};
        if (!SetFileTime(output.handle.value, nullptr, &disabled, &disabled))
            fail("fat_tree_extract_time_control", GetLastError());
        tree->start_content(node.key);
        std::uint64_t position = 0;
        while (!tree->content_finished()) {
            stop();
            fresh();
            output.check();
            auto frame = tree->next_content({}, hooks.stop);
            auto page = field(frame, "page");
            if (!field(page, "applicable").boolean || field(page, "status").text == "partial")
                fail(cancelled_frame(frame) ? "fat_tree_extract_cancelled"
                                            : "fat_tree_extract_content_partial");
            const auto bytes = unhex(field(page, "data").text);
            if (integer(field(page, "file_offset")) != position ||
                bytes.size() > node.bytes - position ||
                hash(bytes.data(), bytes.size()) != field(page, "data_sha256").text)
                fail("fat_tree_extract_content_binding");
            page.fields.erase("data");
            append("content-observation",
                   V::object().put("key", V::string(node.key)).put("page", std::move(page)));
            if (!bytes.empty()) {
                append("intent", intent(node, "write-content")
                                     .put("offset", exact(position))
                                     .put("bytes", exact(bytes.size()))
                                     .put("sha256", V::string(hash(bytes.data(), bytes.size()))));
                stop();
                fresh();
                output.check();
                seek(output.handle.value, position);
                write(output.handle.value, bytes.data(), bytes.size());
                boundary("chunk_written");
                stop();
                flush(output.handle.value);
                boundary("chunk_flushed");
                const auto returned = read(output.handle.value, position, bytes.size());
                if (returned != bytes)
                    fail("fat_tree_extract_destination_verification");
                output.check();
                fresh();
                verified_bytes += bytes.size();
                boundary("chunk_verified");
                append("checkpoint",
                       V::object()
                           .put("key", V::string(node.key))
                           .put("offset", exact(position))
                           .put("bytes", exact(bytes.size()))
                           .put("sha256", V::string(hash(returned.data(), returned.size()))));
                position += bytes.size();
            }
        }
        if (position != node.bytes || f::metadata(output.handle.value).size != node.bytes)
            fail("fat_tree_extract_file_size");
        append("intent", intent(node, "apply-native-metadata"));
        stop();
        fresh();
        output.check();
        auto applied = apply_metadata(output, mapping);
        boundary("metadata_applied");
        flush(output.handle.value);
        append("metadata-result", V::object()
                                      .put("key", V::string(node.key))
                                      .put("identity", output.id)
                                      .put("fields", applied));
        if (!metadata_matches(applied))
            fail("fat_tree_extract_metadata_mismatch");
        append("file-complete", V::object()
                                    .put("key", V::string(node.key))
                                    .put("bytes", exact(position))
                                    .put("identity", output.id));
    }
    V execute(const FatTreeExtractionGrant &grant, const FatTreeExtractionHooks &callbacks) {
        if (executed)
            fail("fat_tree_extract_already_executed");
        if (grant.definition_digest != definition_digest || !grant.source_read ||
            !grant.destination_write || !grant.ledger_write || !grant.host_effects)
            fail("fat_tree_extract_grant");
        if (callbacks.attempt_id.empty() || callbacks.attempt_id.size() > 128 ||
            !json::valid_utf8(callbacks.attempt_id) ||
            callbacks.attempt_id.find_first_of("\r\n\0", 0, 3) != callbacks.attempt_id.npos)
            fail("fat_tree_extract_attempt");
        hooks = callbacks;
        stop();
        fresh();
        if (exists(destination_path.value) || exists(ledger_path.value))
            fail("fat_tree_extract_exists");
        tree->begin_reinspection();
        executed = true;
        std::string status = "complete", diagnostic, domain;
        DWORD platform = 0;
        try {
            effects_possible = true;
            ledger = create_child(ledger_path.parents.back().value, ledger_path.leaf, false);
            ledger_identity = identity(ledger.value, false);
            boundary("ledger_created");
            append("definition", definition);
            append("intent", V::object()
                                 .put("effect", V::string("create-root"))
                                 .put("path", V::string(f::utf8(destination_path.value))));
            stop();
            fresh();
            directories.emplace("root", std::unique_ptr<Owned>(new Owned(
                                            create_child(destination_path.parents.back().value,
                                                         destination_path.leaf, true),
                                            destination_path.value, true)));
            ++directories_done;
            boundary("root_created");
            append("root-created", V::object()
                                       .put("identity", directories.at("root")->id)
                                       .put("source_metadata", V::string("no-root-dirent")));
            std::size_t page_number = 0, node_number = 0;
            std::map<std::string, V> directory_mappings;
            while (!tree->finished()) {
                stop();
                fresh();
                const auto frame = tree->next(hooks.stop);
                const auto &page = field(frame, "page");
                if (!field(page, "applicable").boolean)
                    fail(cancelled_frame(frame) ? "fat_tree_extract_cancelled"
                                                : "fat_tree_extract_execution_source");
                if (page_number == page_events.size() ||
                    hash(encode(field(page, "events"))) != page_events[page_number++])
                    fail("fat_tree_extract_tree_changed");
                append("tree-observation", page);
                for (const auto &record : field(page, "events").items) {
                    if (field(record, "type").text != "record")
                        continue;
                    const auto kind = integer(field(record, "kind"));
                    if ((kind != 3 && kind != 4) || integer(field(record, "dot")))
                        continue;
                    if (node_number == nodes.size())
                        fail("fat_tree_extract_tree_changed");
                    const auto &node = nodes[node_number++];
                    if (node.key != field(record, "key").text ||
                        node.parent != field(record, "directory").text)
                        fail("fat_tree_extract_tree_changed");
                    auto metadata =
                        tree->metadata_candidates(node.key, request.metadata, hooks.stop);
                    const auto mapping = field(metadata, "mapping");
                    if (hash(encode(mapping)) != node.metadata_digest)
                        fail("fat_tree_extract_metadata_changed");
                    append("original-metadata", std::move(metadata));
                    if (!node.directory)
                        file(node, mapping);
                    else {
                        append("intent", intent(node, "create-directory"));
                        stop();
                        fresh();
                        auto parent = directories.find(node.parent);
                        if (parent == directories.end())
                            fail("fat_tree_extract_parent");
                        directories.emplace(node.key, std::unique_ptr<Owned>(new Owned(
                                                          create_child(parent->second->handle.value,
                                                                       node.name, true),
                                                          node.path, true)));
                        ++directories_done;
                        boundary("directory_created");
                        directory_mappings.emplace(node.key, mapping);
                    }
                }
                if (field(page, "status").text == "partial")
                    fail("fat_tree_extract_execution_incomplete");
            }
            if (page_number != page_events.size() || node_number != nodes.size() ||
                verified_bytes != total_bytes)
                fail("fat_tree_extract_tree_incomplete");
            for (auto at = nodes.rbegin(); at != nodes.rend(); ++at)
                if (at->directory) {
                    append("intent", intent(*at, "apply-native-directory-metadata"));
                    stop();
                    fresh();
                    const auto &owned = *directories.at(at->key);
                    auto applied = apply_metadata(owned, directory_mappings.at(at->key));
                    boundary("metadata_applied");
                    append("metadata-result", V::object()
                                                  .put("key", V::string(at->key))
                                                  .put("identity", owned.id)
                                                  .put("fields", applied));
                    if (!metadata_matches(applied))
                        fail("fat_tree_extract_metadata_mismatch");
                }
            append("outcome", outcome_payload("complete", "", 0, ""));
            boundary("complete_flushed");
        } catch (const FatTreeExtractionError &error) {
            status = "partial";
            diagnostic = error.what();
            platform = error.platform_code;
            domain = error.platform_domain;
        } catch (const f::Error &error) {
            status = "partial";
            diagnostic = error.what();
            platform = error.platform_code;
            domain = "win32";
        } catch (const std::exception &error) {
            status = "partial";
            diagnostic = error.what();
        }
        if (diagnostic == "fat_tree_extract_cancelled")
            cancellation_seen = true;
        if (completion_flushed) {
            auto completed = outcome("complete", "", 0, "");
            completed.put("notification_diagnostic",
                          diagnostic.empty() ? V{} : V::string(diagnostic));
            return completed;
        }
        if (status != "complete" && ledger.value != INVALID_HANDLE_VALUE) {
            try {
                append("outcome", outcome_payload(status, diagnostic, platform, domain));
            } catch (...) {
                status = "partial_evidence_uncertain";
            }
        }
        return outcome(status, diagnostic, platform, domain);
    }
    V outcome_payload(const std::string &status, const std::string &diagnostic, DWORD platform,
                      const std::string &domain) const {
        auto value = outcome(status, diagnostic, platform, domain);
        value.put("ledger_records_before_outcome", field(value, "ledger_records"));
        value.put("ledger_bytes_before_outcome", field(value, "ledger_bytes"));
        value.put("last_digest_before_outcome", field(value, "last_record_digest"));
        value.fields.erase("ledger_records");
        value.fields.erase("ledger_bytes");
        value.fields.erase("last_record_digest");
        return value;
    }
    V outcome(const std::string &status, const std::string &diagnostic, DWORD platform,
              const std::string &domain) const {
        return V::object()
            .put("schema", V::string("org.disked.fat-tree-extraction-outcome-prototype/1"))
            .put("status", V::string(status))
            .put("definition_digest", V::string(definition_digest))
            .put("attempt_id", V::string(hooks.attempt_id))
            .put("effects_possible", V::boolean_value(effects_possible))
            .put("cancellation_observed", V::boolean_value(cancellation_seen))
            .put("files_complete", exact(files_done))
            .put("directories_created", exact(directories_done))
            .put("verified_bytes", exact(verified_bytes))
            .put("checkpointed_bytes", exact(checkpointed_bytes))
            .put("ledger_records", exact(sequence))
            .put("ledger_bytes", exact(ledger_bytes))
            .put("last_record_digest", V::string(previous))
            .put("diagnostic", diagnostic.empty() ? V{} : V::string(diagnostic))
            .put("platform_code", exact(platform))
            .put("platform_domain", domain.empty() ? V{} : V::string(domain))
            .put("source_writes", V::boolean_value(false))
            .put("atomic_snapshot", V::boolean_value(false))
            .put("contained_worker_qualified", V::boolean_value(false))
            .put("owner_accepted", V::boolean_value(false));
    }
};
FatTreeExtraction::FatTreeExtraction(const FatTreeExtractionRequest &request)
    : impl_(new Impl(request)) {
}
FatTreeExtraction::~FatTreeExtraction() = default;
const V &FatTreeExtraction::definition() const {
    return impl_->definition;
}
const std::string &FatTreeExtraction::digest() const {
    return impl_->definition_digest;
}
V FatTreeExtraction::execute(const FatTreeExtractionGrant &grant,
                             const FatTreeExtractionHooks &hooks) {
    return impl_->execute(grant, hooks);
}
} // namespace disked
