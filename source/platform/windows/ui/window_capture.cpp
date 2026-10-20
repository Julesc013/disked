#include "window_capture.h"
#include <cstring>

namespace disked { namespace ui {
namespace {
std::wstring object_name(HANDLE object) {
    wchar_t text[256]{};
    DWORD bytes = 0;
    if (!GetUserObjectInformationW(object,UOI_NAME,text,sizeof(text),&bytes) ||
        bytes < sizeof(wchar_t) || bytes > sizeof(text) || text[bytes/sizeof(wchar_t)-1] != L'\0')
        return {};
    return text;
}
bool image_matches(const WindowCaptureRequest& request) {
    wchar_t path[32768]{};
    const auto length = GetModuleFileNameW(nullptr,path,32768);
    if (!length || length >= 32768) return false;
    const auto file = CreateFileW(path,FILE_READ_ATTRIBUTES,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    FILE_ID_INFO info{};
    const bool read = GetFileInformationByHandleEx(file,FileIdInfo,&info,sizeof(info)) != FALSE;
    CloseHandle(file);
    return read && info.VolumeSerialNumber == request.image_volume &&
        std::memcmp(info.FileId.Identifier,request.image_file_id.data(),16) == 0;
}
bool owner_matches(const WindowCaptureRequest& request) {
    DWORD process = 0;
    const auto thread = GetWindowThreadProcessId(request.window,&process);
    BOOL member = FALSE;
    if (!IsWindow(request.window) || process != request.process || process != GetCurrentProcessId() ||
        thread != request.thread || thread != GetCurrentThreadId() ||
        !IsProcessInJob(GetCurrentProcess(),request.job,&member) || !member)
        return false;
    const auto low = static_cast<std::uint32_t>(reinterpret_cast<ULONG_PTR>(GetPropW(request.window,L"DiskEd.Capture.NonceLow")));
    const auto high = static_cast<std::uint32_t>(reinterpret_cast<ULONG_PTR>(GetPropW(request.window,L"DiskEd.Capture.NonceHigh")));
    return (static_cast<std::uint64_t>(high)<<32 | low) == request.nonce &&
        object_name(GetProcessWindowStation())+L"\\"+object_name(GetThreadDesktop(thread)) == request.desktop &&
        image_matches(request);
}
struct Dib {
    HDC dc = nullptr;
    HBITMAP bitmap = nullptr;
    HGDIOBJ prior = nullptr;
    void* bits = nullptr;
    ~Dib() {
        if (prior && prior != HGDI_ERROR) SelectObject(dc,prior);
        if (bitmap) DeleteObject(bitmap);
        if (dc) DeleteDC(dc);
    }
};
}

WindowCaptureResult capture_owned_window_client(const WindowCaptureRequest& request) {
    WindowCaptureResult result;
    if (!request.window || !request.job || !request.process || !request.thread ||
        !request.nonce || request.desktop.empty() || request.desktop.size() > 255 ||
        request.width <= 0 || request.height <= 0 || request.width > 4096 || request.height > 2160 ||
        static_cast<std::uint64_t>(request.width)*request.height*4 > 16*1024*1024)
        return result;
    result.status = WindowCaptureStatus::identity_mismatch;
    if (!owner_matches(request)) return result;
    RECT before{};
    result.status = WindowCaptureStatus::geometry_changed;
    if (!GetClientRect(request.window,&before) || before.left || before.top ||
        before.right != request.width || before.bottom != request.height)
        return result;
    result.status = WindowCaptureStatus::capture_failed;
    result.gdi_before = GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    {
        Dib dib;
        dib.dc = CreateCompatibleDC(nullptr); // A memory DC; never read a display DC.
        if (!dib.dc) return result;
        BITMAPINFO info{};
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = request.width;
        info.bmiHeader.biHeight = -request.height;
        info.bmiHeader.biPlanes = 1;
        info.bmiHeader.biBitCount = 32;
        info.bmiHeader.biCompression = BI_RGB;
        dib.bitmap = CreateDIBSection(dib.dc,&info,DIB_RGB_COLORS,&dib.bits,nullptr,0);
        if (!dib.bitmap || !dib.bits) return result;
        dib.prior = SelectObject(dib.dc,dib.bitmap);
        if (!dib.prior || dib.prior == HGDI_ERROR) return result;
        const auto size = static_cast<std::size_t>(request.width)*request.height*4;
        std::memset(dib.bits,0,size);
        SendMessageW(request.window,WM_PRINTCLIENT,reinterpret_cast<WPARAM>(dib.dc),PRF_CLIENT|PRF_ERASEBKGND);
        RECT after{};
        if (!GdiFlush()) return result;
        if (!owner_matches(request)) { result.status = WindowCaptureStatus::identity_mismatch; return result; }
        if (!GetClientRect(request.window,&after) || std::memcmp(&before,&after,sizeof(before)) != 0) {
            result.status = WindowCaptureStatus::geometry_changed; return result;
        }
        const auto* bytes = static_cast<const unsigned char*>(dib.bits);
        result.bgra.assign(bytes,bytes+size);
    }
    result.gdi_after = GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    result.status = WindowCaptureStatus::captured;
    return result;
}
}}
