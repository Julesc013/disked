#include "window_capture.h"
#include <algorithm>
#include <cstring>

namespace disked { namespace ui {
namespace {
#define CAPTURE_USER(X) X(GetWindowThreadProcessId) X(IsWindow) X(GetPropW) X(GetProcessWindowStation) \
    X(GetThreadDesktop) X(GetUserObjectInformationW) X(GetClientRect) X(GetGuiResources) X(SendMessageW) \
    X(GetWindow) X(GetParent) X(GetWindowRect) X(IsWindowVisible) X(GetClassNameW) X(GetWindowLongW)
#define CAPTURE_GDI(X) X(CreateCompatibleDC) X(CreateDIBSection) X(SelectObject) X(DeleteObject) X(DeleteDC) X(GdiFlush)
struct Api {
    HMODULE user=nullptr,gdi=nullptr;
    bool ready=true;
#define DECLARE(name) decltype(&::name) name=nullptr;
    CAPTURE_USER(DECLARE) CAPTURE_GDI(DECLARE)
#undef DECLARE
    template<class T> void bind(HMODULE module,const char* name,T& output) {
        const auto value=module?GetProcAddress(module,name):nullptr;
        static_assert(sizeof(value)==sizeof(output),"Windows function pointer width");
        std::memcpy(&output,&value,sizeof(value));if(!output)ready=false;
    }
    Api() {
        user=LoadLibraryExW(L"user32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        gdi=LoadLibraryExW(L"gdi32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
#define USER_BIND(name) bind(user,#name,name);
#define GDI_BIND(name) bind(gdi,#name,name);
        CAPTURE_USER(USER_BIND) CAPTURE_GDI(GDI_BIND)
#undef USER_BIND
#undef GDI_BIND
    }
    ~Api(){if(gdi)FreeLibrary(gdi);if(user)FreeLibrary(user);}
};
#undef CAPTURE_USER
#undef CAPTURE_GDI
std::wstring object_name(Api& api,HANDLE object) {
    wchar_t text[256]{};DWORD bytes=0;
    if(!api.GetUserObjectInformationW(object,UOI_NAME,text,sizeof(text),&bytes) ||
       bytes<sizeof(wchar_t) || bytes>sizeof(text) || bytes%sizeof(wchar_t) || text[bytes/sizeof(wchar_t)-1]!=L'\0')return {};
    return text;
}
bool image_matches(const WindowCaptureRequest& request) {
    wchar_t path[32768]{};const auto length=GetModuleFileNameW(nullptr,path,32768);
    if(!length || length>=32768)return false;
    const auto file=CreateFileW(path,FILE_READ_ATTRIBUTES,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    FILE_ID_INFO info{};const bool read=GetFileInformationByHandleEx(file,FileIdInfo,&info,sizeof(info))!=FALSE;
    CloseHandle(file);
    return read && info.VolumeSerialNumber==request.image_volume && std::memcmp(info.FileId.Identifier,request.image_file_id.data(),16)==0;
}
bool owner_matches(Api& api,const WindowCaptureRequest& request) {
    DWORD process=0;const auto thread=api.GetWindowThreadProcessId(request.window,&process);BOOL member=FALSE;
    if(!api.IsWindow(request.window) || process!=request.process || process!=GetCurrentProcessId() ||
       thread!=request.thread || thread!=GetCurrentThreadId() ||
       !IsProcessInJob(GetCurrentProcess(),request.job,&member) || !member)return false;
    const auto low=static_cast<std::uint32_t>(reinterpret_cast<ULONG_PTR>(api.GetPropW(request.window,L"DiskEd.Capture.NonceLow")));
    const auto high=static_cast<std::uint32_t>(reinterpret_cast<ULONG_PTR>(api.GetPropW(request.window,L"DiskEd.Capture.NonceHigh")));
    const auto station=object_name(api,api.GetProcessWindowStation()),desktop=object_name(api,api.GetThreadDesktop(thread));
    return !station.empty() && !desktop.empty() && (static_cast<std::uint64_t>(high)<<32|low)==request.nonce &&
           station+L"\\"+desktop==request.desktop && image_matches(request);
}
struct Child {
    HWND window=nullptr,parent=nullptr;DWORD thread=0,process=0;RECT rect{};bool visible=false;LONG style=0;std::wstring type;
    bool operator==(const Child& other) const {
        return window==other.window && parent==other.parent && thread==other.thread && process==other.process &&
               std::memcmp(&rect,&other.rect,sizeof(rect))==0 && visible==other.visible && style==other.style && type==other.type;
    }
};
WindowCaptureStatus children(Api& api,const WindowCaptureRequest& request,HWND parent,unsigned depth,std::vector<Child>& out) {
    for(auto window=api.GetWindow(parent,GW_CHILD);window;window=api.GetWindow(window,GW_HWNDNEXT)) {
        if(depth>8 || out.size()>=64)return WindowCaptureStatus::invalid_request;
        if(std::any_of(out.begin(),out.end(),[&](const Child& item){return item.window==window;}))return WindowCaptureStatus::identity_mismatch;
        Child item;item.window=window;item.parent=api.GetParent(window);item.thread=api.GetWindowThreadProcessId(window,&item.process);
        if(!api.IsWindow(window) || item.parent!=parent || item.process!=request.process || item.thread!=request.thread)
            return WindowCaptureStatus::identity_mismatch;
        wchar_t type[256]{};const auto length=api.GetClassNameW(window,type,256);
        if(!length || length>=255 || !api.GetWindowRect(window,&item.rect))return WindowCaptureStatus::geometry_changed;
        item.type.assign(type,static_cast<std::size_t>(length));item.visible=api.IsWindowVisible(window)!=FALSE;item.style=api.GetWindowLongW(window,GWL_STYLE);
        out.push_back(item);const auto status=children(api,request,window,depth+1,out);
        if(status!=WindowCaptureStatus::captured)return status;
    }
    return WindowCaptureStatus::captured;
}
struct Dib {
    Api& api;HDC dc=nullptr;HBITMAP bitmap=nullptr;HGDIOBJ prior=nullptr;void* bits=nullptr;
    explicit Dib(Api& value):api(value){}
    ~Dib(){if(prior && prior!=HGDI_ERROR)api.SelectObject(dc,prior);if(bitmap)api.DeleteObject(bitmap);if(dc)api.DeleteDC(dc);}
};
}

WindowCaptureResult capture_owned_window_client(const WindowCaptureRequest& request) {
    WindowCaptureResult result;
    if(!request.window || !request.job || !request.process || !request.thread || !request.nonce ||
       request.desktop.empty() || request.desktop.size()>255 || request.width<=0 || request.height<=0 ||
       request.width>4096 || request.height>2160 || static_cast<std::uint64_t>(request.width)*request.height*4>16*1024*1024)return result;
    Api api;result.status=WindowCaptureStatus::capture_failed;if(!api.ready)return result;
    result.status=WindowCaptureStatus::identity_mismatch;if(!owner_matches(api,request))return result;
    RECT before{};result.status=WindowCaptureStatus::geometry_changed;
    if(!api.GetClientRect(request.window,&before) || before.left || before.top || before.right!=request.width || before.bottom!=request.height)return result;
    std::vector<Child> initial;
    if(request.child_tree){result.status=children(api,request,request.window,1,initial);if(result.status!=WindowCaptureStatus::captured)return result;}
    result.status=WindowCaptureStatus::capture_failed;result.gdi_before=api.GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    {
        Dib dib(api);dib.dc=api.CreateCompatibleDC(nullptr); // Memory DC; no display pixels are read.
        if(!dib.dc)return result;
        BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=request.width;
        info.bmiHeader.biHeight=-request.height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
        dib.bitmap=api.CreateDIBSection(dib.dc,&info,DIB_RGB_COLORS,&dib.bits,nullptr,0);
        if(!dib.bitmap || !dib.bits)return result;
        dib.prior=api.SelectObject(dib.dc,dib.bitmap);if(!dib.prior || dib.prior==HGDI_ERROR)return result;
        const auto size=static_cast<std::size_t>(request.width)*request.height*4;std::memset(dib.bits,0,size);
        api.SendMessageW(request.window,request.child_tree?WM_PRINT:WM_PRINTCLIENT,reinterpret_cast<WPARAM>(dib.dc),
                         PRF_CLIENT|PRF_ERASEBKGND|(request.child_tree?PRF_CHILDREN:0));
        RECT after{};if(!api.GdiFlush())return result;
        if(!owner_matches(api,request)){result.status=WindowCaptureStatus::identity_mismatch;return result;}
        if(!api.GetClientRect(request.window,&after) || std::memcmp(&before,&after,sizeof(before))!=0){result.status=WindowCaptureStatus::geometry_changed;return result;}
        if(request.child_tree){std::vector<Child> final;const auto status=children(api,request,request.window,1,final);
            if(status!=WindowCaptureStatus::captured){result.status=status;return result;}
            if(initial!=final){result.status=WindowCaptureStatus::geometry_changed;return result;}}
        const auto* bytes=static_cast<const unsigned char*>(dib.bits);result.bgra.assign(bytes,bytes+size);
    }
    result.descendants=initial.size();result.gdi_after=api.GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);result.status=WindowCaptureStatus::captured;return result;
}
}}
