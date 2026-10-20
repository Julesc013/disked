#include "platform/windows/ui/window_capture.h"
#include <cstdio>

int main(){
    const auto user=GetModuleHandleW(L"user32.dll"),gdi=GetModuleHandleW(L"gdi32.dll");
    const auto result=disked::ui::capture_owned_window_client({});
    if(result.status!=disked::ui::WindowCaptureStatus::invalid_request || !result.bgra.empty() ||
       GetModuleHandleW(L"user32.dll")!=user || GetModuleHandleW(L"gdi32.dll")!=gdi)return 1;
    std::fputs("capture-lazy-startup-ok\n",stdout);return 0;
}
