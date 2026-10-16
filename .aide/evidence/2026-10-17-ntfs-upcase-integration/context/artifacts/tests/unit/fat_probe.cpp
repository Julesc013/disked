#include "portable/fat/fat.h"
#include "runtime/command/json.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using V = disked::json::Value;
static void require(bool value) {
    if (!value)
        throw std::runtime_error("FAT probe invariant");
}
static const V &field(const V &value, const char *key) {
    const auto *result = value.find(key);
    require(result != nullptr);
    return *result;
}
static de_u64 exact(const V &value) {
    de_u64 result{};
    require(value.kind == V::Kind::string &&
            !de_u64_parse(value.text.data(), value.text.size(), &result));
    return result;
}
static de_u32 small(const V &value) {
    auto number = exact(value);
    de_u32 result = 0;
    require(!de_u64_to_u32(&number, &result));
    return result;
}
static V number(unsigned long value) {
    return V::number(std::to_string(value));
}
static V decimal(const de_u64 &value) {
    char output[21];
    require(!de_u64_format(&value, output, sizeof(output)));
    return V::string(output);
}
static unsigned digit(char value) {
    if (value >= '0' && value <= '9')
        return static_cast<unsigned>(value - '0');
    if (value >= 'a' && value <= 'f')
        return static_cast<unsigned>(value - 'a' + 10);
    throw std::runtime_error("FAT probe hex");
}
static std::vector<unsigned char> unhex(const V &value) {
    require(value.kind == V::Kind::string && value.text.size() % 2 == 0 &&
            value.text.size() <= 2097152);
    std::vector<unsigned char> result(value.text.size() / 2);
    for (std::size_t i = 0; i < result.size(); ++i)
        result[i] = static_cast<unsigned char>(digit(value.text[i * 2]) * 16 +
                                               digit(value.text[i * 2 + 1]));
    return result;
}
static V observe(const V &request) {
    const auto &operation = field(request, "op");
    require(operation.kind == V::Kind::string);
    auto output = V::object();
    if (operation.text == "volume") {
        auto data = unhex(field(request, "boot"));
        const auto before = data;
        de_view view{data.data(), data.size()};
        auto available = exact(field(request, "available"));
        de_fat_volume volume;
        std::memset(&volume, 0xa5, sizeof(volume));
        unsigned char saved[sizeof(volume)];
        std::memcpy(saved, &volume, sizeof(volume));
        auto status = de_fat_volume_read(&view, &available, &volume);
        output.put("status", number(static_cast<unsigned long>(status)));
        if (status)
            require(std::memcmp(saved, &volume, sizeof(volume)) == 0);
        else {
            output.put("issues", number(volume.issues))
                .put("bits", number(static_cast<unsigned long>(volume.bits)))
                .put("usable", V::boolean_value(volume.usable_layout != 0))
                .put("volume_bytes", decimal(volume.volume_bytes))
                .put("fat_bytes", decimal(volume.fat_bytes))
                .put("data_offset_bytes", decimal(volume.data_offset_bytes));
#define REPORT_FAT_FIELD(key) output.put(#key, number(volume.key))
            REPORT_FAT_FIELD(bytes_per_sector);
            REPORT_FAT_FIELD(sectors_per_cluster);
            REPORT_FAT_FIELD(reserved_sectors);
            REPORT_FAT_FIELD(fat_count);
            REPORT_FAT_FIELD(fat_sectors);
            REPORT_FAT_FIELD(total_sectors);
            REPORT_FAT_FIELD(root_entries);
            REPORT_FAT_FIELD(root_sectors);
            REPORT_FAT_FIELD(first_data_sector);
            REPORT_FAT_FIELD(data_sectors);
            REPORT_FAT_FIELD(cluster_count);
            REPORT_FAT_FIELD(cluster_bytes);
            REPORT_FAT_FIELD(root_cluster);
            REPORT_FAT_FIELD(flags);
            REPORT_FAT_FIELD(version);
            REPORT_FAT_FIELD(fsinfo_sector);
            REPORT_FAT_FIELD(backup_sector);
#undef REPORT_FAT_FIELD
            output.put("mirrored", V::boolean_value(volume.mirrored != 0));
        }
        require(before == data);
    } else {
        auto data = unhex(field(request, "fat"));
        const auto before = data;
        de_view view{data.data(), data.size()};
        auto bits = small(field(request, "bits"));
        require(bits <= 64);
        const auto clusters = small(field(request, "clusters"));
        if (operation.text == "entry") {
            de_fat_entry entry;
            std::memset(&entry, 0xa5, sizeof(entry));
            unsigned char saved[sizeof(entry)];
            std::memcpy(saved, &entry, sizeof(entry));
            auto status = de_fat_entry_read(&view, static_cast<int>(bits), clusters,
                                            small(field(request, "index")), &entry);
            output.put("status", number(static_cast<unsigned long>(status)));
            if (status)
                require(std::memcmp(saved, &entry, sizeof(entry)) == 0);
            else
                output.put("index", number(entry.index))
                    .put("raw", number(entry.raw_value))
                    .put("value", number(entry.value))
                    .put("kind", number(static_cast<unsigned long>(entry.kind)));
        } else {
            require(operation.text == "chain");
            auto capacity = small(field(request, "capacity")),
                 budget = small(field(request, "budget"));
            require(capacity <= DE_FAT_MAX_CHAIN);
            std::vector<de_u32> workspace(capacity, 0xdeadbeefUL);
            const auto saved_workspace = workspace;
            de_u32 dummy = 0xdeadbeefUL;
            de_fat_chain chain;
            std::memset(&chain, 0xa5, sizeof(chain));
            unsigned char saved[sizeof(chain)];
            std::memcpy(saved, &chain, sizeof(chain));
            auto status = de_fat_chain_read(
                &view, static_cast<int>(bits), clusters, small(field(request, "start")),
                capacity ? workspace.data() : &dummy, capacity, budget, &chain);
            output.put("status", number(static_cast<unsigned long>(status)));
            if (status)
                require(std::memcmp(saved, &chain, sizeof(chain)) == 0 &&
                        workspace == saved_workspace);
            else {
                auto rows = V::array();
                require(chain.count <= capacity);
                for (std::size_t i = 0; i < chain.count; ++i)
                    rows.items.push_back(number(workspace[i]));
                for (std::size_t i = chain.count; i < workspace.size(); ++i)
                    require(workspace[i] == saved_workspace[i]);
                output.put("prefix", rows)
                    .put("disposition", number(static_cast<unsigned long>(chain.disposition)))
                    .put("stopped_cluster", number(chain.stopped_cluster))
                    .put("terminal_value", number(chain.terminal_value))
                    .put("terminal_kind", number(static_cast<unsigned long>(chain.terminal_kind)));
            }
            require(dummy == 0xdeadbeefUL);
        }
        require(before == data);
    }
    return output;
}

static int guard() {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    require(info.dwPageSize >= 4096);
    auto *pages = static_cast<unsigned char *>(
        VirtualAlloc(nullptr, info.dwPageSize * 3, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    require(pages != nullptr);
    auto *boundary = pages + info.dwPageSize * 2;
    DWORD old = 0;
    auto *boot = boundary - 512;
    boot[11] = 0;
    boot[12] = 2;
    boot[13] = 1;
    boot[14] = 1;
    boot[16] = 2;
    boot[17] = 224;
    boot[19] = 0x40;
    boot[20] = 0x0b;
    boot[22] = 9;
    boot[510] = 0x55;
    boot[511] = 0xaa;
    require(VirtualProtect(pages, info.dwPageSize * 2, PAGE_READONLY, &old) != 0);
    require(VirtualProtect(boundary, info.dwPageSize, PAGE_NOACCESS, &old) != 0);
    auto available = de_u64_from_u32(1474560);
    de_fat_volume volume{};
    de_view view{boot, 512};
    require(!de_fat_volume_read(&view, &available, &volume) && volume.usable_layout);
    for (std::size_t size = 0; size < 512; ++size) {
        de_view short_view{boundary - size, size};
        require(!de_fat_volume_read(&short_view, &available, &volume) &&
                volume.issues == DE_FAT_TRUNCATED);
    }
    de_view overlong{boundary, 4097};
    unsigned char saved[sizeof(volume)];
    std::memcpy(saved, &volume, sizeof(volume));
    require(de_fat_volume_read(&overlong, &available, &volume) == DE_BOUNDS &&
            std::memcmp(saved, &volume, sizeof(volume)) == 0);
    for (int bits : {12, 16, 32}) {
        const de_u32 clusters = bits == 12 ? 2847 : (bits == 16 ? 5000 : 65525);
        const std::size_t length = bits == 12 ? 5 : (bits == 16 ? 6 : 12);
        de_fat_entry entry{};
        for (std::size_t size = 0; size < length; ++size) {
            de_view short_view{boundary - size, size};
            unsigned char saved_entry[sizeof(entry)];
            std::memcpy(saved_entry, &entry, sizeof(entry));
            require(de_fat_entry_read(&short_view, bits, clusters, 2, &entry) == DE_BOUNDS &&
                    std::memcmp(saved_entry, &entry, sizeof(entry)) == 0);
        }
        de_view inaccessible{boundary, length};
        de_u32 workspace[2]{123, 456};
        de_fat_chain chain{};
        unsigned char saved_chain[sizeof(chain)];
        std::memcpy(saved_chain, &chain, sizeof(chain));
        require(de_fat_chain_read(&inaccessible, bits, clusters, 2, workspace, 1, 2, &chain) ==
                    DE_BUFFER &&
                workspace[0] == 123 && workspace[1] == 456 &&
                std::memcmp(saved_chain, &chain, sizeof(chain)) == 0);
    }
    require(VirtualFree(pages, 0, MEM_RELEASE) != 0);
    std::puts(
        "FAT C/C++ linkage, protected read-only bounds and capacity-before-read checks passed.");
    return 0;
}

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--guard")
            return guard();
        require(argc == 1);
        disked::json::Limits limits;
        limits.bytes = 3 * 1024 * 1024;
        limits.string_bytes = 2 * 1024 * 1024;
        limits.values = 4096;
        std::string line;
        while (std::getline(std::cin, line)) {
            require(line.size() <= limits.bytes);
            std::cout << disked::json::dump(observe(disked::json::parse(line, limits)), limits)
                      << '\n';
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
