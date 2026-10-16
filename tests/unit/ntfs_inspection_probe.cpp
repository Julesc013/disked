#include "runtime/capture/ntfs_inspection.h"
#include <iostream>

namespace {
using V = disked::json::Value;
const V &field(const V &value, const char *key) {
    const auto *found = value.find(key);
    if (!found)
        throw std::invalid_argument("probe_shape");
    return *found;
}
} // namespace
int main() {
    try {
        std::string input;
        char byte;
        while (std::cin.get(byte)) {
            if (input.size() == 8U * 1024U * 1024U)
                return 2;
            input += byte;
        }
        disked::json::Limits limits;
        limits.bytes = 8U * 1024U * 1024U;
        limits.string_bytes = 6U * 1024U * 1024U;
        limits.values = 524288;
        limits.depth = 48;
        const auto request = disked::json::parse(input, limits);
        if (const auto *kind = request.find("private_kind")) {
            if (kind->kind != V::Kind::string ||
                (kind->text != "upcase" && kind->text != "unknown"))
                throw std::invalid_argument("probe_kind");
            disked::NtfsInspectionRequest selected;
            selected.path = "not-opened";
            selected.volume_bytes = 512;
            selected.kind = kind->text == "upcase" ? disked::NtfsSnapshotKind::Upcase
                                                   : static_cast<disked::NtfsSnapshotKind>(99);
            auto result = V::object().put("rejected", V::boolean_value(false));
            try {
                disked::validate_ntfs_inspection_request(selected);
            } catch (const std::invalid_argument &error) {
                result.put("rejected", V::boolean_value(true))
                    .put("diagnostic", V::string(error.what()));
            }
            std::cout << disked::json::dump(result) << '\n';
            return 0;
        }
        bool called = false;
        const auto out = disked::dispatch_ntfs_inspection(
            "probe", field(request, "parameters"), [&](const disked::NtfsInspectionRequest &) {
                called = true;
                disked::NtfsInspectionRead read;
                const auto &status = field(request, "status");
                if (status.kind != V::Kind::string)
                    throw std::invalid_argument("probe_status");
                if (status.text == "captured") {
                    read.status = disked::NtfsInspectionRead::Status::Captured;
                    read.file = field(request, "file");
                } else if (status.text == "refused")
                    read.status = disked::NtfsInspectionRead::Status::Refused;
                else if (status.text != "unresolved")
                    throw std::invalid_argument("probe_status");
                if (const auto *context = request.find("context"))
                    read.context = *context;
                if (const auto *worker = request.find("worker"))
                    read.worker = *worker;
                if (const auto *diagnostic = request.find("diagnostic"))
                    read.diagnostic = diagnostic->text;
                return read;
            });
        std::cout << disked::json::dump(
                         V::object()
                             .put("port_called", V::boolean_value(called))
                             .put("exit_code", V::number(std::to_string(out.exit_code)))
                             .put("wire_bytes", V::number(std::to_string(
                                                    disked::response_frame(out.response).size())))
                             .put("response", out.response),
                         limits)
                  << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
