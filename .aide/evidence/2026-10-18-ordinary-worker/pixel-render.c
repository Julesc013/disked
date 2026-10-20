/* Private x64 known-pixel fixture, never part of the product composition.
 * The sender validates the exact owned job/window/desktop before installing
 * this thread-specific hook. No display read, input hook, or global hook.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <wchar.h>

typedef struct {
    DWORD magic, version;
    uint64_t window;
    DWORD pid, width, height, bytes;
    uint64_t first, second;
    volatile LONG status;
    DWORD error, renderer_pid, renderer_thread;
    BYTE reserved[32];
} Frame;
typedef char frame_is_96_bytes[(sizeof(Frame) == 96) ? 1 : -1];

static void render(const CWPSTRUCT *message)
{
    wchar_t name[96], class_name[64];
    DWORD pid = 0, error = 0;
    RECT rect, client;
    HANDLE section = NULL;
    Frame *frame = NULL;
    HDC dc = NULL;
    HBITMAP bitmap = NULL;
    HGDIOBJ previous = NULL;
    void *bits = NULL;
    BITMAPINFO info = {0};
    uint64_t first = (uint64_t)message->wParam;
    uint64_t second = (uint64_t)message->lParam;
    /* This control-only candidate cannot operate on arbitrary applications. */
    if (GetWindowThreadProcessId(message->hwnd, &pid) != GetCurrentThreadId() ||
        pid != GetCurrentProcessId() ||
        !GetClassNameW(message->hwnd, class_name, 64) ||
        wcscmp(class_name, L"DiskEdPixelOriginControl") != 0 ||
        !GetWindowRect(message->hwnd, &rect) ||
        !GetClientRect(message->hwnd, &client) ||
        rect.right - rect.left != 240 || rect.bottom - rect.top != 96 ||
        client.left != 0 || client.top != 0 || client.right != 240 || client.bottom != 96)
        return;
    if (swprintf_s(name, 96, L"Local\\DiskEdPixel-%016llx%016llx", first, second) < 0)
        return;
    section = OpenFileMappingW(FILE_MAP_READ | FILE_MAP_WRITE, FALSE, name);
    if (!section) return;
    frame = (Frame *)MapViewOfFile(section, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, 96 + 92160);
    if (!frame) goto done;
    if (frame->magic != 0x50454444 || frame->version != 1 ||
        frame->window != (uint64_t)(UINT_PTR)message->hwnd || frame->pid != pid ||
        frame->width != 240 || frame->height != 96 || frame->bytes != 92160 ||
        frame->first != first || frame->second != second ||
        InterlockedCompareExchange(&frame->status, 1, 0) != 0)
        goto done;
    frame->renderer_pid = GetCurrentProcessId();
    frame->renderer_thread = GetCurrentThreadId();
    dc = CreateCompatibleDC(NULL);
    if (!dc) { error = GetLastError(); goto complete; }
    info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth = 240;
    info.bmiHeader.biHeight = -96;
    info.bmiHeader.biPlanes = 1;
    info.bmiHeader.biBitCount = 32;
    info.bmiHeader.biCompression = BI_RGB;
    info.bmiHeader.biSizeImage = 92160;
    bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &bits, section, 96);
    if (!bitmap || !bits) { error = GetLastError(); goto complete; }
    previous = SelectObject(dc, bitmap);
    if (!previous || previous == HGDI_ERROR) { error = ERROR_INVALID_HANDLE; goto complete; }
    ZeroMemory(bits, 92160);
    /* The memory DC is created and consumed in this UI thread/process. */
    SendMessageW(message->hwnd, WM_PRINT, (WPARAM)dc,
                 PRF_NONCLIENT | PRF_CLIENT | PRF_ERASEBKGND | PRF_CHILDREN);
    if (!GdiFlush()) error = GetLastError();
complete:
    if (previous && previous != HGDI_ERROR) SelectObject(dc, previous);
    if (bitmap) DeleteObject(bitmap);
    if (dc) DeleteDC(dc);
    frame->error = error;
    InterlockedExchange(&frame->status, error ? 3 : 2);
done:
    if (frame) UnmapViewOfFile(frame);
    CloseHandle(section);
}

__declspec(dllexport) LRESULT CALLBACK OwnedPixelHook(int code, WPARAM wp, LPARAM lp)
{
    /* No User32 work from DllMain. All non-fixture messages pass unchanged. */
    if (code >= 0 && lp) {
        const CWPSTRUCT *message = (const CWPSTRUCT *)lp;
        UINT request = RegisterWindowMessageW(L"DiskEd.OwnedPixelFixture/1");
        if (request && message->message == request) render(message);
    }
    return CallNextHookEx(NULL, code, wp, lp);
}
