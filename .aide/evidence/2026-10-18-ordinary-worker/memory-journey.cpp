// Executes the unchanged production component; opens no product/storage files.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "platform/windows/memory_budget.h"
#include <cstdio>

int main() {
    disked::WindowsMemoryBudget budget;
    SetLastError(0);
    const auto user=LoadLibraryExW(L"user32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    const auto user_error=user?0:GetLastError();
    std::printf("{\"ready\":%s,\"process_limit_bytes\":\"%llu\",\"platform_error\":%lu,\"error\":\"%s\",\"private_job\":%s,\"user32_loaded\":%s,\"user32_error\":%lu}\n",
        budget.ready()?"true":"false",
        static_cast<unsigned long long>(budget.limit_bytes()),budget.platform_error(),
        budget.error()?budget.error():"",budget.uses_private_job()?"true":"false",user?"true":"false",static_cast<unsigned long>(user_error));
    if(user)FreeLibrary(user);
    return budget.ready() && user?0:3;
}
