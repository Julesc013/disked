#include "ntfs_probe_support.h"
#include <memory>

namespace {
struct Table {
    std::vector<unsigned char> original;
    std::vector<std::unique_ptr<Guard>> storage;
    std::vector<de_view> pages;
    de_ntfs_upcase handle{};

    explicit Table(const std::vector<unsigned char> &raw) : original(raw) {
        need(raw.size() == DE_NTFS_UPCASE_BYTES);
        for (std::size_t index = 0; index < DE_NTFS_UPCASE_PAGES; ++index) {
            const auto begin = raw.begin() + index * DE_NTFS_UPCASE_PAGE_BYTES;
            std::vector<unsigned char> page(begin, begin + DE_NTFS_UPCASE_PAGE_BYTES);
            // Alternate exact right guards with deliberately unaligned views.
            if (index % 2)
                page.push_back(0xB7);
            storage.emplace_back(new Guard(page));
            pages.push_back({storage.back()->data, DE_NTFS_UPCASE_PAGE_BYTES});
        }
        need(de_ntfs_upcase_init(pages.data(), pages.size(), 3, 1, &handle) == DE_OK);
    }
    void preserved() const {
        for (std::size_t index = 0; index < pages.size(); ++index) {
            need(std::memcmp(storage[index]->data,
                             original.data() + index * DE_NTFS_UPCASE_PAGE_BYTES,
                             DE_NTFS_UPCASE_PAGE_BYTES) == 0);
            if (index % 2)
                need(storage[index]->data[DE_NTFS_UPCASE_PAGE_BYTES] == 0xB7);
        }
    }
};

template <class T> struct Slot {
    unsigned char prefix[16];
    T value;
    unsigned char suffix[16];
    Slot() {
        std::memset(this, 0xA5, sizeof(*this));
    }
    void unchanged() const {
        const auto bytes = reinterpret_cast<const unsigned char *>(this);
        for (std::size_t i = 0; i < sizeof(*this); ++i)
            need(bytes[i] == 0xA5);
    }
    void bounded() const {
        for (auto byte : prefix)
            need(byte == 0xA5);
        for (auto byte : suffix)
            need(byte == 0xA5);
    }
};

V run(const V &request) {
    Table table(unhex(get(request, "table_hex"), DE_NTFS_UPCASE_BYTES));
    std::vector<unsigned char> mapped(DE_NTFS_UPCASE_BYTES);
    const auto handle_before = table.handle;
    for (de_u32 unit = 0; unit < DE_NTFS_UPCASE_UNITS; ++unit) {
        Slot<unsigned short> output;
        need(de_ntfs_upcase_read(&table.handle, unit, &output.value) == DE_OK);
        output.bounded();
        mapped[unit * 2] = static_cast<unsigned char>(output.value & 255U);
        mapped[unit * 2 + 1] = static_cast<unsigned char>(output.value >> 8);
    }
    auto orders = V::array();
    const auto &queries = get(request, "queries");
    need(queries.kind == V::Kind::array && queries.items.size() <= 4096);
    for (const auto &query : queries.items) {
        const auto a = unhex(get(query, "left_hex"), 510);
        const auto b = unhex(get(query, "right_hex"), 510);
        Guard left(a), right(b);
        const de_view av{left.data, a.size()}, bv{right.data, b.size()};
        Slot<de_ntfs_name_order> output;
        need(de_ntfs_name_compare(&table.handle, &av, &bv, &output.value) == DE_OK);
        output.bounded();
        const auto first = output.value;
        need(de_ntfs_name_compare(&table.handle, &av, &bv, &output.value) == DE_OK);
        need(output.value.raw_order == first.raw_order &&
             output.value.upcase_order == first.upcase_order);
        orders.items.push_back(
            V::object()
                .put("raw_order", V::number(std::to_string(first.raw_order)))
                .put("upcase_order", V::number(std::to_string(first.upcase_order))));
        need(a.empty() || std::memcmp(left.data, a.data(), a.size()) == 0);
        need(b.empty() || std::memcmp(right.data, b.data(), b.size()) == 0);
    }
    need(table.handle.pages == handle_before.pages &&
         table.handle.page_count == handle_before.page_count &&
         table.handle.major == handle_before.major && table.handle.minor == handle_before.minor);
    table.preserved();
    return V::object()
        .put("mapped_hex", V::string(hex(mapped.data(), mapped.size())))
        .put("orders", std::move(orders));
}

void guards() {
    // Supplied all-zero mappings deliberately disagree with host ASCII rules.
    Table table(std::vector<unsigned char>(DE_NTFS_UPCASE_BYTES, 0));
    unsigned count = 0;
    const de_view empty{nullptr, 0};
    auto bad_handle = [&](const de_ntfs_upcase *handle, int expected) {
        Slot<unsigned short> word;
        Slot<de_ntfs_name_order> order;
        need(de_ntfs_upcase_read(handle, 0, &word.value) == expected);
        word.unchanged();
        need(de_ntfs_name_compare(handle, &empty, &empty, &order.value) == expected);
        order.unchanged();
        count += 2;
    };
    auto bad_init = [&](const de_view *pages, std::size_t page_count, unsigned major,
                        unsigned minor, int expected) {
        Slot<de_ntfs_upcase> output;
        need(de_ntfs_upcase_init(pages, page_count, major, minor, &output.value) == expected);
        output.unchanged();
        ++count;
    };
    bad_handle(nullptr, DE_INVALID);
    bad_init(nullptr, 256, 3, 1, DE_INVALID);
    for (auto page_count : {std::size_t(0), std::size_t(255), std::size_t(257)}) {
        bad_init(table.pages.data(), page_count, 3, 1, DE_BOUNDS);
        auto handle = table.handle;
        handle.page_count = page_count;
        bad_handle(&handle, DE_BOUNDS);
    }
    for (const auto version :
         {std::make_pair(2U, 1U), std::make_pair(3U, 2U), std::make_pair(4U, 0U)}) {
        bad_init(table.pages.data(), 256, version.first, version.second, DE_INVALID);
        auto handle = table.handle;
        handle.major = version.first;
        handle.minor = version.second;
        bad_handle(&handle, DE_INVALID);
    }
    for (auto index : {std::size_t(0), std::size_t(127), std::size_t(255)}) {
        const auto original = table.pages[index];
        for (auto size : {std::size_t(0), std::size_t(511), std::size_t(513)}) {
            table.pages[index].size = size;
            bad_init(table.pages.data(), 256, 3, 1, DE_BOUNDS);
            bad_handle(&table.handle, DE_BOUNDS);
        }
        table.pages[index] = {nullptr, 512};
        bad_init(table.pages.data(), 256, 3, 1, DE_INVALID);
        bad_handle(&table.handle, DE_INVALID);
        table.pages[index] = original;
    }
    auto no_pages = table.handle;
    no_pages.pages = nullptr;
    bad_handle(&no_pages, DE_INVALID);
    for (de_u32 unit : {de_u32(65536UL), de_u32(0xFFFFFFFFUL)}) {
        Slot<unsigned short> output;
        need(de_ntfs_upcase_read(&table.handle, unit, &output.value) == DE_BOUNDS);
        output.unchanged();
        ++count;
    }
    Guard name(std::vector<unsigned char>(512, 0));
    for (auto view : {de_view{nullptr, 2}, de_view{name.data, 1}, de_view{name.data, 509},
                      de_view{name.data, 512}}) {
        const auto expected = view.data == nullptr ? DE_INVALID : DE_BOUNDS;
        for (unsigned side = 0; side < 2; ++side) {
            Slot<de_ntfs_name_order> output;
            need(de_ntfs_name_compare(&table.handle, side ? &empty : &view, side ? &view : &empty,
                                      &output.value) == expected);
            output.unchanged();
            ++count;
        }
    }
    for (unsigned side = 0; side < 2; ++side) {
        Slot<de_ntfs_name_order> output;
        need(de_ntfs_name_compare(&table.handle, side ? &empty : nullptr, side ? nullptr : &empty,
                                  &output.value) == DE_INVALID);
        output.unchanged();
        ++count;
    }
    need(de_ntfs_upcase_init(table.pages.data(), 256, 3, 1, nullptr) == DE_INVALID);
    need(de_ntfs_upcase_read(&table.handle, 0, nullptr) == DE_INVALID);
    need(de_ntfs_name_compare(&table.handle, &empty, &empty, nullptr) == DE_INVALID);
    count += 3;
    for (unsigned minor : {0U, 1U}) {
        Slot<de_ntfs_upcase> output;
        need(de_ntfs_upcase_init(table.pages.data(), 256, 3, minor, &output.value) == DE_OK);
        output.bounded();
        Slot<de_ntfs_name_order> order;
        need(de_ntfs_name_compare(&output.value, &empty, &empty, &order.value) == DE_OK);
        need(order.value.raw_order == 0 && order.value.upcase_order == 0);
        order.bounded();
        count += 2;
    }
    table.preserved();
    std::cout << "{\"status\":\"pass\",\"guard_cases\":" << count << "}\n";
}
} // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::strcmp(argv[1], "--guard") == 0)
            guards();
        else {
            need(argc == 1);
            process_rows(run);
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
