#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

int wmain(int argc, wchar_t **argv) {
    if (argc != 2) return 2;
    HANDLE token = NULL;
    DWORD bytes = 0, container = 0;
    TOKEN_ELEVATION elevation = {};
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) return 3;
    const BOOL container_ok = GetTokenInformation(token, TokenIsAppContainer, &container, sizeof(container), &bytes);
    const BOOL elevation_ok = GetTokenInformation(token, TokenElevation, &elevation, sizeof(elevation), &bytes);
    CloseHandle(token);
    if (!container_ok || !elevation_ok) return 4;
    HANDLE outside = CreateFileW(argv[1], GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    const DWORD denied = outside == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    if (outside != INVALID_HANDLE_VALUE) CloseHandle(outside);
    ULARGE_INTEGER available = {}, total = {}, free_bytes = {};
    if (!GetDiskFreeSpaceExW(L".", &available, &total, &free_bytes)) return 5;
    printf("{\"pointer_bits\":%u,\"msc_full_ver\":%u,\"appcontainer\":%lu,\"elevated\":%lu,\"outside_error\":%lu,\"volume_bytes\":%llu}\n",
           static_cast<unsigned>(8 * sizeof(void *)), static_cast<unsigned>(_MSC_FULL_VER),
           static_cast<unsigned long>(container), static_cast<unsigned long>(elevation.TokenIsElevated),
           static_cast<unsigned long>(denied), static_cast<unsigned long long>(total.QuadPart));
    return container == 1 && elevation.TokenIsElevated == 0 && denied == ERROR_ACCESS_DENIED &&
           total.QuadPart <= 512ULL * 1024 * 1024 ? 0 : 6;
}
