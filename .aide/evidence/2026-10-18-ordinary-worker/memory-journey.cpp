// Executes the unchanged production component; opens no product/storage files.
#include "platform/windows/memory_budget.h"
#include <cstdio>

int main() {
    disked::WindowsMemoryBudget budget;
    std::printf("{\"ready\":%s,\"process_limit_bytes\":\"%llu\",\"platform_error\":%lu,\"error\":\"%s\",\"private_job\":%s}\n",
        budget.ready()?"true":"false",
        static_cast<unsigned long long>(budget.limit_bytes()),budget.platform_error(),
        budget.error()?budget.error():"",budget.uses_private_job()?"true":"false");
    return budget.ready()?0:3;
}
