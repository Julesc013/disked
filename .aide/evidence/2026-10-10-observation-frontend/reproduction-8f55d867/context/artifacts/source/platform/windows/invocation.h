#pragma once
#include "policy.h"
namespace disked {
InvocationHost observe_windows_invocation();
int windows_entry(int argc,wchar_t** argv);
}
