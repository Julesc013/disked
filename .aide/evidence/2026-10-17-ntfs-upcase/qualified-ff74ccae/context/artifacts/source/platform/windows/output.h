#pragma once
#include <cstdio>
#include <string>
namespace disked {
// Single sequential standard-stream writer. Failure seals the channel: never
// append a replacement frame after a possibly partial write. No FILE* is used
// by the background thread, so CRT stream cleanup cannot wait on its stdio lock.
class WindowsOutput final {
    FILE* stream_;
    bool failed_=false;
public:
    explicit WindowsOutput(FILE* stream):stream_(stream) {}
    WindowsOutput(const WindowsOutput&)=delete;
    WindowsOutput& operator=(const WindowsOutput&)=delete;
    bool write(std::string bytes) noexcept;
};
}
