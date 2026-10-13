#include "runtime/capture/fat_content_stream.h"
#include <algorithm>
#include <iostream>
#include <vector>
using V = disked::json::Value;
using Bytes = std::vector<unsigned char>;
static void require(bool ok) {
    if (!ok)
        throw std::runtime_error("content stream probe invariant");
}
static const V &field(const V &v, const char *key) {
    const auto *p = v.find(key);
    require(p != nullptr);
    return *p;
}
static std::uint64_t integer(const V &v) {
    require(v.kind == V::Kind::string && disked::json::decimal_u64(v.text));
    return std::stoull(v.text);
}
static std::uint64_t native(const de_u64 &n) {
    char text[21];
    require(!de_u64_format(&n, text, sizeof(text)));
    return std::stoull(text);
}
static Bytes unhex(const V &v) {
    require(v.kind == V::Kind::string && v.text.size() % 2 == 0);
    Bytes out(v.text.size() / 2);
    auto digit = [](char c) {
        require((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
        return unsigned(c <= '9' ? c - '0' : c - 'a' + 10);
    };
    for (std::size_t i = 0; i < out.size(); ++i)
        out[i] = static_cast<unsigned char>(digit(v.text[2 * i]) * 16 + digit(v.text[2 * i + 1]));
    return out;
}
struct Region {
    std::uint64_t offset;
    Bytes bytes;
};
struct Pattern {
    std::uint64_t offset, bytes, salt;
};
int main() {
    try {
        disked::json::Limits limits;
        limits.bytes = 16777216;
        limits.values = 262144;
        limits.depth = 32;
        limits.string_bytes = 4194304;
        std::string text((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(text, limits);
        disked::FatContentStreamSelection s;
        s.binding.source_id = "fixture-source";
        s.binding.capture_id = "fixture-capture";
        s.binding.epoch = 17;
        s.binding.source_bytes = integer(field(input, "source_bytes"));
        s.binding.volume_offset = integer(field(input, "offset"));
        s.binding.volume_bytes = integer(field(input, "length"));
        s.binding.fat_copy = static_cast<std::uint32_t>(integer(field(input, "copy")));
        s.record_source_offset = integer(field(input, "record_offset"));
        const auto raw = unhex(field(input, "record"));
        require(raw.size() == 32);
        std::copy(raw.begin(), raw.end(), s.record.begin());
        std::vector<Region> regions;
        for (const auto &r : field(input, "regions").items)
            regions.push_back({integer(field(r, "offset")), unhex(field(r, "hex"))});
        std::vector<Pattern> patterns;
        if (const auto *list = input.find("patterns"))
            for (const auto &r : list->items)
                patterns.push_back({integer(field(r, "offset")), integer(field(r, "bytes")),
                                    integer(field(r, "salt"))});
        disked::FatContentStreamBudget budget;
        if (const auto *b = input.find("budget")) {
            if (const auto *v = b->find("bytes"))
                budget.bytes = static_cast<std::size_t>(integer(*v));
            if (const auto *v = b->find("reads"))
                budget.reads = static_cast<std::size_t>(integer(*v));
            if (const auto *v = b->find("read_bytes"))
                budget.read_bytes = static_cast<std::size_t>(integer(*v));
            if (const auto *v = b->find("cells"))
                budget.cells = static_cast<std::size_t>(integer(*v));
            if (const auto *v = b->find("output_bytes"))
                budget.output_bytes = static_cast<std::size_t>(integer(*v));
        }
        const auto maximum = input.find("bitmap_bytes")
                                 ? static_cast<std::size_t>(integer(field(input, "bitmap_bytes")))
                                 : 67108864U;
        const auto *fault = input.find("fault");
        const auto mode = fault ? field(*fault, "mode").text : std::string{};
        const auto at = fault ? integer(field(*fault, "at")) : 0;
        std::uint64_t calls = 0, reads = 0;
        Bytes buffer;
        disked::FatTraversalPort port;
        port.applicable = [&](const disked::FatTraversalBinding &b) {
            require(b.source_id == s.binding.source_id && b.epoch == 17);
            ++calls;
            if (mode == "applicable_throw" && calls >= at)
                throw std::runtime_error("fixture callback");
            return !(mode == "withdraw" && calls >= at);
        };
        port.read = [&](const de_byte_extent &extent) {
            const auto first = native(extent.start), last = native(extent.end);
            ++reads;
            require(last >= first && last - first <= 4096 && first >= s.binding.volume_offset &&
                    last <= s.binding.source_bytes);
            require(std::string(extent.space->name, extent.space->name_length) ==
                    s.binding.source_id);
            if (mode == "reader_throw" && reads == at)
                throw std::runtime_error("fixture read");
            buffer.assign(static_cast<std::size_t>(last - first), 0);
            for (const auto &p : patterns)
                for (std::size_t i = 0; i < buffer.size(); ++i)
                    if (first + i >= p.offset && first + i - p.offset < p.bytes)
                        buffer[i] = static_cast<unsigned char>(((first + i - p.offset) * 37 +
                                                                ((first + i - p.offset) >> 8) * 11 +
                                                                p.salt) %
                                                               256);
            for (const auto &r : regions) {
                const auto begin = (std::max)(first, r.offset),
                           end = (std::min)(last, r.offset + r.bytes.size());
                if (begin < end)
                    std::copy(r.bytes.begin() + static_cast<std::size_t>(begin - r.offset),
                              r.bytes.begin() + static_cast<std::size_t>(end - r.offset),
                              buffer.begin() + static_cast<std::size_t>(begin - first));
            }
            if (reads == at) {
                if (mode == "short" && !buffer.empty())
                    buffer.pop_back();
                if (mode == "overlong")
                    buffer.push_back(0);
                if ((mode == "record_change" || mode == "boot_change") && !buffer.empty())
                    buffer[0] ^= 1;
            }
            return de_view{buffer.data(), buffer.size()};
        };
        std::size_t refused = 0;
        auto invalid = s;
        invalid.binding.epoch = 0;
        try {
            disked::FatContentStream wrong(invalid, port);
            require(false);
        } catch (const disked::FatContentStreamError &) {
            ++refused;
        }
        require(reads == 0 && calls == 0);
        disked::FatContentStream stream(s, port, maximum);
        auto reject = [&] {
            std::vector<disked::FatContentStreamSelection> wrong(9, s);
            wrong[0].binding.source_id += 'x';
            wrong[1].binding.capture_id += 'x';
            ++wrong[2].binding.epoch;
            ++wrong[3].binding.source_bytes;
            ++wrong[4].binding.volume_offset;
            ++wrong[5].binding.volume_bytes;
            ++wrong[6].binding.fat_copy;
            ++wrong[7].record_source_offset;
            wrong[8].record[0] ^= 1;
            const auto before_reads = reads, before_calls = calls;
            for (const auto &value : wrong)
                try {
                    stream.next(value, budget);
                    require(false);
                } catch (const disked::FatContentStreamError &) {
                    ++refused;
                }
            auto bad = budget;
            bad.reads = 0;
            try {
                stream.next(s, bad);
                require(false);
            } catch (const disked::FatContentStreamError &) {
                ++refused;
            }
            require(reads == before_reads && calls == before_calls);
        };
        reject();
        std::uint64_t pages = 0;
        do {
            auto page = stream.next(s, budget);
            std::cout
                << disked::json::dump(
                       V::object().put("kind", V::string("page")).put("page", std::move(page)),
                       limits)
                << '\n';
            require(++pages < 1000000);
            if (pages == 1)
                reject();
        } while (!stream.finished());
        const auto before_reads = reads, before_calls = calls;
        auto terminal = stream.next(s, budget);
        require(reads == before_reads && calls == before_calls);
        require(terminal.fields.at("returned_bytes").text == "0");
        std::cout << disked::json::dump(V::object()
                                            .put("kind", V::string("summary"))
                                            .put("pages", V::string(std::to_string(pages)))
                                            .put("refused", V::string(std::to_string(refused)))
                                            .put("reads", V::string(std::to_string(reads)))
                                            .put("callbacks", V::string(std::to_string(calls)))
                                            .put("terminal", std::move(terminal)),
                                        limits)
                  << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
