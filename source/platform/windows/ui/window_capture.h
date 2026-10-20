#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace disked { namespace ui {
// Private Windows 10 prototype. The coordinator owns the queried job and pins
// the exact image file against writes/deletion. No public capture API is admitted.
struct WindowCaptureRequest {
    HWND window = nullptr;
    DWORD process = 0, thread = 0;
    HANDLE job = nullptr; // Borrowed JOB_OBJECT_QUERY handle.
    std::wstring desktop; // Exact window-station\desktop name.
    std::uint64_t nonce = 0, image_volume = 0;
    std::array<unsigned char,16> image_file_id{};
    int width = 0, height = 0;
    bool child_tree = false; // At most64 descendants/eight levels; same UI thread.
};
enum class WindowCaptureStatus { captured, invalid_request, identity_mismatch, geometry_changed, capture_failed };
struct WindowCaptureResult {
    WindowCaptureStatus status = WindowCaptureStatus::invalid_request;
    DWORD gdi_before = 0, gdi_after = 0;
    std::size_t descendants = 0;
    std::vector<unsigned char> bgra;
};
// Must run on the window's owning UI thread. GDI objects remain in this process;
// only pixels leave it. Delivery/paint success is not independent pixel evidence.
WindowCaptureResult capture_owned_window_client(const WindowCaptureRequest& request);
// Private test transport, not a public message/API contract. Numeric handles
// are borrowed; the coordinator creates, transfers and retires capabilities.
constexpr ULONG_PTR window_capture_message=0x44454331;
struct WindowCaptureReceiver {
    std::uint32_t attempts=0,sequence=0;
    std::uint64_t nonce=0;
    bool busy=false;
};
bool receive_owned_window_capture(HWND window,const COPYDATASTRUCT& packet,
                                  WindowCaptureReceiver& state,bool enabled) noexcept;
}}
