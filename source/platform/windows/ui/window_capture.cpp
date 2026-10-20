#include "window_capture.h"
#include <algorithm>
#include <climits>
#include <cstring>

namespace disked { namespace ui {
namespace {
#define CAPTURE_USER(X) X(GetWindowThreadProcessId) X(IsWindow) X(GetPropW) X(GetProcessWindowStation) \
    X(GetThreadDesktop) X(GetUserObjectInformationW) X(GetClientRect) X(GetGuiResources) X(SendMessageW) \
    X(GetWindow) X(GetParent) X(GetWindowRect) X(IsWindowVisible) X(GetClassNameW) X(GetWindowLongW) X(ClientToScreen)
#define CAPTURE_GDI(X) X(CreateCompatibleDC) X(CreateDIBSection) X(SelectObject) X(DeleteObject) X(DeleteDC) X(GdiFlush) X(SetViewportOrgEx)
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
        if(request.child_tree) {
            RECT frame{};POINT origin{};
            if(!api.GetWindowRect(request.window,&frame) || !api.ClientToScreen(request.window,&origin))return result;
            const auto x=static_cast<std::int64_t>(frame.left)-origin.x,y=static_cast<std::int64_t>(frame.top)-origin.y;
            if(x<INT_MIN || x>INT_MAX || y<INT_MIN || y>INT_MAX){result.status=WindowCaptureStatus::geometry_changed;return result;}
            // Align WM_PRINT's window origin with the client-only bitmap.
            if(!api.SetViewportOrgEx(dib.dc,static_cast<int>(x),static_cast<int>(y),nullptr))return result;
        }
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
namespace {
std::uint32_t u32(const unsigned char* p){std::uint32_t n=0;for(unsigned i=0;i<4;++i)n|=static_cast<std::uint32_t>(p[i])<<(i*8);return n;}
std::uint64_t u64(const unsigned char* p){return u32(p)|(static_cast<std::uint64_t>(u32(p+4))<<32);}
void put32(unsigned char* p,std::uint32_t n){for(unsigned i=0;i<4;++i)p[i]=static_cast<unsigned char>(n>>(i*8));}
void put64(unsigned char* p,std::uint64_t n){put32(p,static_cast<std::uint32_t>(n));put32(p+4,static_cast<std::uint32_t>(n>>32));}
LONG signed32(const unsigned char* p){const auto n=u32(p);return static_cast<LONG>(n<=0x7fffffff?n:static_cast<std::int64_t>(n)-0x100000000LL);}
struct View{void* value=nullptr;~View(){if(value)UnmapViewOfFile(value);}};
struct Busy{bool& value;explicit Busy(bool& p):value(p){value=true;}~Busy(){value=false;}};
}
bool receive_owned_window_capture(HWND window,const COPYDATASTRUCT& packet,WindowCaptureReceiver& state,bool enabled) noexcept {
    try {
        if(!enabled || packet.dwData!=window_capture_message || packet.cbData!=640 || !packet.lpData || state.busy || state.attempts>=8)return false;
        ++state.attempts;std::array<unsigned char,640> bytes{};std::memcpy(bytes.data(),packet.lpData,bytes.size());const auto* p=bytes.data();
        if(std::memcmp(p,"DECAPR1\0",8)!=0 || std::any_of(p+632,p+640,[](unsigned char c){return c!=0;}))return false;
        const auto nonce=u64(p+8);const auto sequence=u32(p+16),width=u32(p+20),height=u32(p+24),units=u32(p+28);
        if(!static_cast<std::uint32_t>(nonce) || !static_cast<std::uint32_t>(nonce>>32) ||
           !sequence || sequence!=state.sequence+1 || (state.nonce && state.nonce!=nonce) ||
           !width || width>4096 || !height || height>2160 || static_cast<std::uint64_t>(width)*height*4>16777216 || !units || units>255 ||
           u64(p+32)!=reinterpret_cast<ULONG_PTR>(window) || u32(p+40)!=GetCurrentProcessId() || u32(p+44)!=GetCurrentThreadId() ||
           !u64(p+48) || !u64(p+56) || u64(p+48)>UINTPTR_MAX || u64(p+56)>UINTPTR_MAX ||
           std::all_of(p+88,p+104,[](unsigned char c){return c==0;}))return false;
        std::wstring desktop;for(std::uint32_t i=0;i<units;++i){const auto c=static_cast<wchar_t>(p[120+i*2]|(static_cast<unsigned>(p[121+i*2])<<8));if(!c)return false;desktop.push_back(c);}
        if(std::any_of(p+120+units*2,p+632,[](unsigned char c){return c!=0;}))return false;
        WindowCaptureRequest request;request.window=window;request.process=u32(p+40);request.thread=u32(p+44);
        request.job=reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(u64(p+48)));request.desktop=desktop;request.nonce=nonce;
        request.image_volume=u64(p+64);std::copy_n(p+72,16,request.image_file_id.begin());request.width=static_cast<int>(width);request.height=static_cast<int>(height);request.child_tree=true;
        RECT expected{signed32(p+104),signed32(p+108),signed32(p+112),signed32(p+116)},before{};
        Api api;if(!api.ready || !owner_matches(api,request) || !api.GetWindowRect(window,&before) || std::memcmp(&before,&expected,sizeof(before))!=0)return false;
        const auto pixel_bytes=width*height*4,total=4096+pixel_bytes;
        View view;view.value=MapViewOfFile(reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(u64(p+56))),FILE_MAP_WRITE,0,0,total);
        if(!view.value)return false;
        MEMORY_BASIC_INFORMATION memory{};
        if(VirtualQuery(view.value,&memory,sizeof(memory))!=sizeof(memory) || memory.State!=MEM_COMMIT || memory.Type!=MEM_MAPPED ||
           memory.Protect!=PAGE_READWRITE || memory.RegionSize<total)return false;
        Busy busy(state.busy);state.sequence=sequence;state.nonce=nonce;
        const auto result=capture_owned_window_client(request);RECT after{};
        if(result.status!=WindowCaptureStatus::captured || result.bgra.size()!=pixel_bytes ||
           !api.GetWindowRect(window,&after) || std::memcmp(&before,&after,sizeof(before))!=0)return false;
        auto* out=static_cast<unsigned char*>(view.value);std::memset(out,0,4096);std::memcpy(out,"DECAPS1\0",8);
        put64(out+8,nonce);put32(out+16,sequence);put32(out+20,width);put32(out+24,height);put32(out+28,pixel_bytes);
        put64(out+32,reinterpret_cast<ULONG_PTR>(window));put32(out+40,request.process);put32(out+44,request.thread);put64(out+48,request.image_volume);
        std::memcpy(out+56,p+72,16);std::memcpy(out+72,p+88,16);put32(out+88,static_cast<std::uint32_t>(result.descendants));
        put32(out+92,result.gdi_before);put32(out+96,result.gdi_after);put32(out+100,1);std::memcpy(out+104,p+104,16);
        std::memcpy(out+4096,result.bgra.data(),pixel_bytes);MemoryBarrier();InterlockedExchange(reinterpret_cast<volatile LONG*>(out+120),static_cast<LONG>(total));return true;
    }catch(...){return false;}
}
}}
