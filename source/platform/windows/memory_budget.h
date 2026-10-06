#pragma once
#include <cstdint>
namespace disked {
// Windows fake-composition admission, not a portable allocator or security fence.
class WindowsMemoryBudget final {
    void* job_=nullptr;
    const char* error_="memory_budget_unavailable";
    unsigned long platform_=0;
    std::uint64_t probe_bytes_=0;
public:
    static constexpr std::uint64_t limit_bytes() {return 256*1024*1024;}
    WindowsMemoryBudget() noexcept;
    ~WindowsMemoryBudget();
    WindowsMemoryBudget(const WindowsMemoryBudget&)=delete;
    WindowsMemoryBudget& operator=(const WindowsMemoryBudget&)=delete;
    bool ready() const {return error_==nullptr;}
    const char* error() const {return error_;}
    unsigned long platform_error() const {return platform_;}
    std::uint64_t probe_bytes() const {return probe_bytes_;}
};
}
