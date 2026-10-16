#include "runtime/capture/fat_retention.h"
#include "runtime/capture/fat_inspection.h"
#include "portable/hash/sha256.h"
#include <atomic>
#include <iostream>
#include <thread>
using namespace disked;
using V = json::Value;
namespace {
std::size_t checks = 0;
void require(bool value) {
    ++checks;
    if (!value)
        throw std::runtime_error("retention_test");
}
template <class F> void error(const char *code, F action) {
    bool caught = false;
    try {
        action();
    } catch (const FatRetentionError &e) {
        caught = std::string(e.what()) == code;
    }
    require(caught);
}
const V &field(const V &value, const char *name) {
    return value.fields.at(name);
}
std::string digest(const std::string &bytes) {
    unsigned char hash[32];
    sha256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), hash);
    std::string out = "sha256:";
    const char hex[] = "0123456789abcdef";
    for (auto c : hash) {
        out += hex[c >> 4];
        out += hex[c & 15];
    }
    return out;
}
std::string decode(const std::string &hex) {
    std::string out;
    out.reserve(hex.size() / 2);
    auto digit = [](char c) { return c <= '9' ? c - '0' : c - 'a' + 10; };
    for (std::size_t i = 0; i < hex.size(); i += 2)
        out += static_cast<char>((digit(hex[i]) << 4) | digit(hex[i + 1]));
    return out;
}
} // namespace
int main() {
    try {
        std::size_t calls = 0;
        FatCaptureStore store([&] {
            ++calls;
            return std::string(32, 'a');
        });
        require(calls == 0 && field(store.list(), "captures").items.empty());
        const auto id = store.reserve("origin");
        require(calls == 1 && valid_fat_capture_id(id));
        require(field(field(store.list(), "captures").items[0], "state").text == "reserved");
        error("capture_retention_busy", [&] { store.release(id); });
        error("capture_retention_busy", [&] { store.read(id, 0, 1); });
        const std::string unicode = "A\xe7\x95\x8c\xf0\x9f\x99\x82Z";
        auto record = V::object()
                          .put("synthetic_only", V::boolean_value(true))
                          .put("unicode", V::string(unicode));
        auto padding = V::array();
        for (int n = 0; n < 20; ++n)
            padding.items.push_back(V::string(std::string(20000, 'x')));
        record.put("padding", std::move(padding));
        const auto receipt = store.commit(id, record);
        std::string restored;
        std::uint64_t offset = 0;
        for (;;) {
            const auto chunk = store.read(id, offset, FatCaptureStore::chunk_bytes);
            const auto part = decode(field(chunk, "data").text);
            require(field(chunk, "chunk_sha256").text == digest(part));
            require(response_frame(completed("read", chunk).response).size() <= 524288);
            restored += part;
            if (field(chunk, "next_offset").kind == V::Kind::null)
                break;
            offset = std::stoull(field(chunk, "next_offset").text);
        }
        json::Limits limits;
        limits.bytes = 8388608;
        limits.string_bytes = 8388608;
        limits.values = 524288;
        limits.depth = 40;
        require(restored == json::dump(record, limits));
        require(digest(restored) == field(receipt, "sha256").text);
        const auto first = restored.find(unicode);
        require(first != std::string::npos);
        for (std::size_t i = first; i < first + unicode.size(); ++i)
            require(decode(field(store.read(id, i, 1), "data").text) == restored.substr(i, 1));
        require(field(store.read(id, restored.size(), 1), "data").text.empty());
        error("capture_retention_range", [&] { store.read(id, restored.size() + 1, 1); });
        error("invalid_parameter", [&] { store.read(id, 0, 196609); });
        error("invalid_parameter", [&] { store.read(id, 0, 0); });
        const auto second = store.reserve("second"), third = store.reserve("third"),
                   fourth = store.reserve("fourth");
        error("capture_retention_resource", [&] { store.reserve("fifth"); });
        store.abandon(second);
        const auto fifth = store.reserve("fifth");
        require(fifth != second && calls == 1);
        error("capture_retention_resource",
              [&] { store.commit(fifth, V::string(std::string(8388608, 'x'))); });
        require(field(store.list(), "captures").items.size() == 4);
        store.abandon(fifth);
        store.abandon(third);
        store.abandon(fourth);
        require(store.release(id).fields.at("released").boolean);
        error("capture_retention_unknown", [&] { store.read(id, 0, 1); });
        error("capture_retention_unknown", [&] { store.release(id); });
        require(
            !valid_fat_capture_id("fat-capture:" + std::string(32, 'a') + ":18446744073709551616"));
        require(
            valid_fat_capture_id("fat-capture:" + std::string(32, 'a') + ":18446744073709551615"));
        require(!valid_fat_capture_id("fat-capture:" + std::string(32, 'a') + ":01"));
        require(dispatch_fat_capture("r", "image.capture.inspect",
                                     V::object().put("phase", V::string("release")), store)
                    .exit_code == 2);
        FatCaptureStore other([] { return std::string(32, 'b'); });
        const auto next = store.reserve("next");
        store.commit(next, V::string("retained"));
        error("capture_retention_unknown", [&] { other.read(next, 0, 1); });
        FatCaptureStore broken([] { return std::string("bad"); });
        error("capture_retention_identity", [&] { broken.reserve("r"); });
        require(field(broken.list(), "captures").items.empty());
        std::atomic<int> finished{0};
        std::vector<std::thread> readers;
        for (int n = 0; n < 4; ++n)
            readers.emplace_back([&] {
                for (int j = 0; j < 100; ++j)
                    if (field(store.read(next, 0, 1), "data").text == "22")
                        ++finished;
            });
        for (auto &reader : readers)
            reader.join();
        require(finished == 400);
        const auto maximum = store.reserve("maximum");
        const auto maximum_receipt =
            store.commit(maximum, V::string(std::string(FatCaptureStore::record_bytes - 2, 'm')));
        require(field(maximum_receipt, "bytes").text == "8388608");
        std::string full;
        std::uint64_t maximum_offset = 0;
        std::size_t chunks = 0;
        for (;;) {
            const auto chunk = store.read(maximum, maximum_offset, FatCaptureStore::chunk_bytes);
            ++chunks;
            require(response_frame(completed("max", chunk).response).size() <= 524288);
            full += decode(field(chunk, "data").text);
            if (field(chunk, "next_offset").kind == V::Kind::null)
                break;
            maximum_offset = std::stoull(field(chunk, "next_offset").text);
        }
        require(chunks == 43 && full.size() == FatCaptureStore::record_bytes);
        require(digest(full) == field(maximum_receipt, "sha256").text);
        FatCaptureStore lifecycle([] {return std::string(32, 'c');});
        auto request=V::object().put("path",V::string("synthetic-only.img")).put("view",V::string("fat"))
            .put("volume_offset",V::string("0")).put("volume_bytes",V::string("1024"))
            .put("retain_capture",V::string("yes"));
        const auto refused_capture=dispatch_fat_inspection("refused",request,[](const FatInspectionRequest&){
            FatInspectionRead out;out.status=FatInspectionRead::Status::Refused;return out;},&lifecycle);
        require(refused_capture.exit_code==3 && field(lifecycle.list(),"captures").items.empty());
        const auto unresolved_capture=dispatch_fat_inspection("unresolved",request,[](const FatInspectionRequest&){return FatInspectionRead{};},&lifecycle);
        require(unresolved_capture.exit_code==6 && field(lifecycle.list(),"captures").items.empty());
        const auto exception_capture=dispatch_fat_inspection("exception",request,[](const FatInspectionRequest&)->FatInspectionRead{
            throw std::runtime_error("synthetic port error");},&lifecycle);
        require(exception_capture.exit_code==4 && field(lifecycle.list(),"captures").items.empty());
        std::cout << "{\"passed\":true,\"maximum_chunks\":43,\"checks\":" << checks
                  << ",\"concurrent_reads\":400,\"scope\":\"synthetic store; no source provenance "
                     "qualification\"}\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
