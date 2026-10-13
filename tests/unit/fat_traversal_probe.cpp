#include "runtime/capture/fat_traversal.h"
#include <algorithm>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using V = disked::json::Value;
static void check(bool ok) {
    if (!ok)
        throw std::runtime_error("fat traversal probe invariant");
}
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    check(p != nullptr);
    return *p;
}
static std::uint64_t integer(const V &v) {
    check(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static std::uint64_t native(const de_u64 &n) {
    char s[21];
    check(!de_u64_format(&n, s, sizeof(s)));
    return std::stoull(s);
}
static unsigned digit(char c) {
    check((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    return static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
}
static std::vector<unsigned char> unhex(const V &v) {
    check(v.kind == V::Kind::string && v.text.size() % 2 == 0);
    std::vector<unsigned char> bytes(v.text.size() / 2);
    for (std::size_t i = 0; i < bytes.size(); ++i)
        bytes[i] = static_cast<unsigned char>(digit(v.text[i * 2]) * 16 + digit(v.text[i * 2 + 1]));
    return bytes;
}
struct Region {
    std::uint64_t offset;
    std::vector<unsigned char> bytes;
};
static V observe(const V &input) {
    disked::FatTraversalBinding b;
    b.source_id = "fixture-source";
    b.capture_id = "fixture-capture";
    b.epoch = 17;
    b.source_bytes = integer(field(input, "source_bytes"));
    b.volume_offset = integer(field(input, "offset"));
    b.volume_bytes = integer(field(input, "length"));
    b.fat_copy = static_cast<std::uint32_t>(integer(field(input, "copy")));
    std::vector<Region> regions;
    for (const auto &r : field(input, "regions").items)
        regions.push_back({integer(field(r, "offset")), unhex(field(r, "hex"))});
    const auto before = regions;
    disked::FatTraversalResources resources;
    if (const auto *r = input.find("resources")) {
        if (const auto *p = r->find("bitmap_bytes"))
            resources.bitmap_bytes = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("queued_directories"))
            resources.queued_directories = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("depth"))
            resources.depth = static_cast<std::size_t>(integer(*p));
    }
    disked::FatTraversalPageBudget budget;
    if (const auto *r = input.find("budget")) {
        if (const auto *p = r->find("records"))
            budget.records = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("events"))
            budget.events = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("reads"))
            budget.reads = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("read_bytes"))
            budget.read_bytes = static_cast<std::size_t>(integer(*p));
        if (const auto *p = r->find("output_bytes"))
            budget.output_bytes = static_cast<std::size_t>(integer(*p));
    }
    const auto *fault = input.find("fault");
    const auto fault_mode = fault ? field(*fault, "mode").text : std::string{};
    const auto fault_at = fault ? integer(field(*fault, "at")) : 0;
    std::uint64_t reads = 0, callbacks = 0;
    auto read_trace = V::array();
    std::vector<unsigned char> buffer;
    disked::FatTraversalPort port;
    port.applicable = [&](const disked::FatTraversalBinding &binding) {
        check(binding.source_id == b.source_id && binding.epoch == b.epoch);
        ++callbacks;
        if (fault_mode == "applicable_throw" && callbacks >= fault_at)
            throw std::runtime_error("fixture epoch observation");
        return !(fault_mode == "withdraw" && callbacks >= fault_at);
    };
    port.read = [&](const de_byte_extent &extent) {
        const auto first = native(extent.start), last = native(extent.end);
        check(extent.space &&
              std::string(extent.space->name, extent.space->name_length) == b.source_id &&
              last >= first && last - first <= 4096 && last <= b.source_bytes);
        ++reads;
        read_trace.items.push_back(V::object()
                                       .put("offset", V::string(std::to_string(first)))
                                       .put("bytes", V::string(std::to_string(last - first))));
        if (fault_mode == "reader_throw" && reads == fault_at)
            throw std::runtime_error("fixture read failure");
        buffer.assign(static_cast<std::size_t>(last - first), 0);
        for (const auto &region : regions) {
            const auto begin = std::max(first, region.offset),
                       end = std::min(last, region.offset + region.bytes.size());
            if (begin < end)
                std::copy(region.bytes.begin() + static_cast<std::size_t>(begin - region.offset),
                          region.bytes.begin() + static_cast<std::size_t>(end - region.offset),
                          buffer.begin() + static_cast<std::size_t>(begin - first));
        }
        if (reads == fault_at) {
            if (fault_mode == "short" && !buffer.empty())
                buffer.pop_back();
            if (fault_mode == "empty")
                buffer.clear();
            if (fault_mode == "overlong")
                buffer.push_back(0);
            if (fault_mode == "boot_change" && !buffer.empty())
                buffer[0] ^= 1;
        }
        return de_view{buffer.data(), buffer.size()};
    };
    const auto initial_reads = reads, initial_callbacks = callbacks;
    auto invalid_binding = b;
    for (const std::string &name : {std::string(129, 'x'), std::string("bad\0id", 6),
                                    std::string(1, static_cast<char>(0xc0))}) {
        invalid_binding.source_id = name;
        try {
            disked::FatTraversal invalid(invalid_binding, port, resources);
            check(false);
        } catch (const disked::FatTraversalError &e) {
            check(std::string(e.what()) == "fat_traversal_binding");
        }
    }
    auto invalid_port = port;
    invalid_port.applicable = {};
    try {
        disked::FatTraversal invalid(b, invalid_port, resources);
        check(false);
    } catch (const disked::FatTraversalError &e) {
        check(std::string(e.what()) == "fat_traversal_port");
    }
    invalid_port = port;
    invalid_port.read = {};
    try {
        disked::FatTraversal invalid(b, invalid_port, resources);
        check(false);
    } catch (const disked::FatTraversalError &e) {
        check(std::string(e.what()) == "fat_traversal_port");
    }
    check(reads == initial_reads && callbacks == initial_callbacks);
    auto pages = V::array();
    disked::FatTraversal traversal(b, port, resources);
    std::size_t rejected = 0;
    // Every coordinate belongs to this exact scope; invalid calls neither read
    // nor advance. Repeat before/after the first real page to cover continuations.
    auto reject = [&] {
        std::vector<disked::FatTraversalBinding> wrong(7, b);
        wrong[0].source_id += "x";
        wrong[1].capture_id += "x";
        ++wrong[2].epoch;
        ++wrong[3].source_bytes;
        ++wrong[4].volume_offset;
        ++wrong[5].volume_bytes;
        ++wrong[6].fat_copy;
        const auto previous_reads = reads, previous_callbacks = callbacks;
        for (const auto &binding : wrong) {
            try {
                traversal.next(binding, budget);
                check(false);
            } catch (const disked::FatTraversalError &e) {
                check(std::string(e.what()) == "fat_traversal_binding_mismatch");
                ++rejected;
            }
        }
        check(reads == previous_reads && callbacks == previous_callbacks);
        auto invalid = budget;
        invalid.records = 0;
        try {
            traversal.next(b, invalid);
            check(false);
        } catch (const disked::FatTraversalError &e) {
            check(std::string(e.what()) == "fat_traversal_page_budget");
        }
        check(reads == previous_reads && callbacks == previous_callbacks);
    };
    reject();
    while (!traversal.finished()) {
        check(pages.items.size() < 50000);
        pages.items.push_back(traversal.next(b, budget));
        if (pages.items.size() == 1 && !traversal.finished()) {
            reject();
            auto relocated = std::move(traversal);
            check(traversal.finished());
            try {
                traversal.next(b, budget);
                check(false);
            } catch (const disked::FatTraversalError &e) {
                check(std::string(e.what()) == "fat_traversal_moved");
            }
            traversal = std::move(relocated);
        }
    }
    const auto previous_reads = reads, previous_callbacks = callbacks;
    try {
        traversal.next(b, budget);
        check(false);
    } catch (const disked::FatTraversalError &e) {
        check(std::string(e.what()) == "fat_traversal_finished");
    }
    check(reads == previous_reads && callbacks == previous_callbacks);
    check(regions.size() == before.size());
    for (std::size_t i = 0; i < regions.size(); ++i)
        check(regions[i].offset == before[i].offset && regions[i].bytes == before[i].bytes);
    return V::object()
        .put("pages", std::move(pages))
        .put("reads", std::move(read_trace))
        .put("binding_refusals", V::string(std::to_string(rejected)));
}
int main() {
    try {
        disked::json::Limits limits;
        limits.bytes = 33554432;
        limits.string_bytes = 8388608;
        limits.values = 2097152;
        limits.depth = 24;
        std::string line;
        while (std::getline(std::cin, line))
            std::cout << disked::json::dump(observe(disked::json::parse(line, limits)), limits)
                      << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
