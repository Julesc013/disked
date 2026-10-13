#include "platform/windows/storage/fat_tree_reconnect.h"
#include "runtime/acquisition/fat_tree_operation.h"
#include <iostream>

using V = disked::json::Value;
static const V &get(const V &v, const char *k) {
    const auto *p = v.find(k);
    if (!p)
        throw std::runtime_error("reconnect_probe_shape");
    return *p;
}
int main() {
    try {
        auto limits = disked::fat_tree_operation::header_limits();
        limits.bytes = 2097152;
        limits.string_bytes = 1048576;
        const std::string raw((std::istreambuf_iterator<char>(std::cin)), {});
        const auto input = disked::json::parse(raw, limits);
        V result;
        if (const auto *h = input.find("header"))
            result =
                disked::fat_tree_operation::read_history(*h, get(input, "history").text).view();
        else
            result = disked::nt_inventory::observe_fat_tree_operation(
                get(input, "operation_id").text, get(input, "store").text,
                input.find("cancel") && input.find("cancel")->boolean);
        std::cout << disked::json::dump(result, limits) << '\n';
        return 0;
    } catch (const std::exception &e) {
        std::cout << disked::json::dump(V::object().put("error", V::string(e.what()))) << '\n';
        return 20;
    }
}
