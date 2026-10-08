#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "gui.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <io.h>

namespace disked {
using json::Value;
namespace {
struct Failure : std::runtime_error {
    int code;Failure(const char* message,int value=4):std::runtime_error(message),code(value){}
};
#define USER_APIS(X) \
    X(GetProcessWindowStation) X(GetUserObjectInformationW) X(RegisterClassW) X(UnregisterClassW) \
    X(CreateWindowExW) X(DestroyWindow) X(DefWindowProcW) X(ShowWindow) X(UpdateWindow) \
    X(GetMessageW) X(TranslateMessage) X(DispatchMessageW) X(IsDialogMessageW) X(PostQuitMessage) X(SetTimer) X(KillTimer) \
    X(SendMessageW) X(SetWindowTextW) X(GetWindowTextW) X(GetWindowTextLengthW) \
    X(GetClientRect) X(MoveWindow) X(SetFocus) X(GetFocus) X(EnableWindow) \
    X(LoadCursorW) X(LoadIconW) X(SystemParametersInfoW) X(GetSysColorBrush) \
    X(GetSysColor) X(InvalidateRect) X(GetDlgCtrlID) X(IsWindow) X(GetWindowRect) X(GetNextDlgTabItem) X(GetKeyState) X(GetDC) X(ReleaseDC)
#define GDI_APIS(X) X(CreateFontIndirectW) X(DeleteObject) X(SetTextColor) X(SetBkColor) X(SelectObject) X(GetTextExtentPoint32W)
class Api final {
    HMODULE user_=nullptr,gdi_=nullptr;
    template<class T> void bind(HMODULE module,const char* name,T& output,bool required=true) {
        const auto proc=GetProcAddress(module,name);static_assert(sizeof(proc)==sizeof(output),"Windows function pointer width");
        std::memcpy(&output,&proc,sizeof(proc));if(required && !output)throw Failure("gui_api_unavailable",3);
    }
public:
#define DECLARE(name) decltype(&::name) name=nullptr;
    USER_APIS(DECLARE) GDI_APIS(DECLARE)
    DECLARE(SetThreadDpiAwarenessContext) DECLARE(GetDpiForWindow)
#undef DECLARE
    Api() {
        try {
#ifdef DISKED_GUI_TEST_UNAVAILABLE
            throw Failure("gui_dependency_unavailable",3);
#else
            user_=LoadLibraryExW(L"user32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
            if(!user_)throw Failure("gui_user32_unavailable",3);
            gdi_=LoadLibraryExW(L"gdi32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
            if(!gdi_)throw Failure("gui_gdi32_unavailable",3);
#define BIND_USER(name) bind(user_,#name,name);
#define BIND_GDI(name) bind(gdi_,#name,name);
            USER_APIS(BIND_USER) GDI_APIS(BIND_GDI)
#undef BIND_USER
#undef BIND_GDI
            bind(user_,"SetThreadDpiAwarenessContext",SetThreadDpiAwarenessContext,false);
            bind(user_,"GetDpiForWindow",GetDpiForWindow,false);
#endif
        } catch(...) {if(gdi_)FreeLibrary(gdi_);if(user_)FreeLibrary(user_);throw;}
    }
    ~Api() {if(gdi_)FreeLibrary(gdi_);if(user_)FreeLibrary(user_);}
};
std::wstring wide(const std::string& value) {
    if(value.empty())return {};
    const auto size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),nullptr,0);
    if(!size)throw Failure("gui_text_encoding");
    std::wstring result(static_cast<std::size_t>(size),L'\0');
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),&result[0],size))throw Failure("gui_text_encoding");
    return result;
}
std::string utf8(const std::wstring& value) {
    if(value.empty())return {};
    const auto size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),nullptr,0,nullptr,nullptr);
    if(!size)return std::string(4097,'?');
    std::string result(static_cast<std::size_t>(size),'\0');
    if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),&result[0],size,nullptr,nullptr))throw Failure("gui_text_encoding");
    return result;
}
enum Control {Navigator=100,Details,Summary,Notice,Targets,Commands,Refresh,Clear,Open,Review,Submit,Back,Heading,PreviousFields,NextFields,FieldPage,
    Field0=200,Field1,Label0=220,Label1};
class Window;
thread_local Window* current=nullptr;
class Window final {
public:
    Api& api;std::unique_ptr<GuiModel> model;
    HWND window=nullptr;HFONT font=nullptr;DPI_AWARENESS_CONTEXT prior_dpi=nullptr;
    std::map<int,HWND> controls;
    bool registered=false,updating=false,failed=false;
    bool contrast_known=false,high_contrast=false;
    UINT dpi=96;std::vector<std::string> ids,fields;
    std::size_t field_page=0;
    const wchar_t* class_name=L"DiskEd.Native.Fake.1";
    Window(Api& a):api(a) {}
    ~Window() {
        if(window && api.IsWindow(window))api.DestroyWindow(window);
        if(font)api.DeleteObject(font);
        if(registered)api.UnregisterClassW(class_name,GetModuleHandleW(nullptr));
        if(prior_dpi && api.SetThreadDpiAwarenessContext)api.SetThreadDpiAwarenessContext(prior_dpi);
        current=nullptr;
    }
    Value observe() {
        USEROBJECTFLAGS flags={};DWORD size=0;
        if(!api.GetUserObjectInformationW(api.GetProcessWindowStation(),UOI_FLAGS,&flags,sizeof(flags),&size) || !(flags.dwFlags&WSF_VISIBLE))
            throw Failure("gui_display_unavailable",3);
        if(api.SetThreadDpiAwarenessContext)prior_dpi=api.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_SYSTEM_AWARE);
        read_contrast();
        return Value::object().put("backend",Value::string("win32-native"))
            .put("window_station_visible",Value::boolean_value(true))
            .put("high_contrast",contrast_known?Value::boolean_value(high_contrast):Value{})
            .put("dpi_mode",Value::string(prior_dpi?"system-aware":"host-default-virtualized"))
            .put("dependency_scope",Value::string("system32-user32-gdi32"));
    }
    void read_contrast() {
        HIGHCONTRASTW value={sizeof(value),0,nullptr};
        contrast_known=api.SystemParametersInfoW(SPI_GETHIGHCONTRAST,sizeof(value),&value,0)!=FALSE;
        high_contrast=contrast_known && (value.dwFlags&HCF_HIGHCONTRASTON)!=0;
    }
    HWND add(int id,const wchar_t* type,const wchar_t* label,DWORD style,DWORD extended=0) {
        HWND child=api.CreateWindowExW(extended,type,label,WS_CHILD|WS_VISIBLE|style,0,0,1,1,window,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(nullptr),nullptr);
        if(!child)throw Failure("gui_control_creation");controls[id]=child;return child;
    }
    void create_controls() {
        add(Targets,L"BUTTON",L"&Targets",WS_TABSTOP|BS_PUSHBUTTON);
        add(Commands,L"BUTTON",L"&Commands",WS_TABSTOP|BS_PUSHBUTTON);
        add(Refresh,L"BUTTON",L"Re&fresh view",WS_TABSTOP|BS_PUSHBUTTON);
        add(Clear,L"BUTTON",L"C&lear selection",WS_TABSTOP|BS_PUSHBUTTON);
        add(Heading,L"STATIC",L"&Navigator",SS_LEFT);
        add(Navigator,L"LISTBOX",L"Navigator",WS_TABSTOP|WS_VSCROLL|WS_HSCROLL|LBS_NOTIFY|LBS_NOINTEGRALHEIGHT,WS_EX_CLIENTEDGE);
        add(Open,L"BUTTON",L"&Inspect / Open",WS_TABSTOP|BS_PUSHBUTTON);
        add(Summary,L"STATIC",L"",SS_LEFT);
        add(Details,L"EDIT",L"",WS_TABSTOP|ES_MULTILINE|ES_READONLY|ES_AUTOHSCROLL|ES_AUTOVSCROLL|WS_HSCROLL|WS_VSCROLL,WS_EX_CLIENTEDGE);
        for(int i=0;i<2;++i) {
            add(Label0+i,L"STATIC",L"",SS_LEFT);
            add(Field0+i,L"EDIT",L"",WS_TABSTOP|ES_AUTOHSCROLL,WS_EX_CLIENTEDGE);
            // A truncated paste still exceeds the admitted UTF-8 limit and is
            // refused. It cannot silently become a valid shortened identity.
            api.SendMessageW(controls.at(Field0+i),EM_SETLIMITTEXT,4097,0);
        }
        add(PreviousFields,L"BUTTON",L"&Previous fields",WS_TABSTOP|BS_PUSHBUTTON);
        add(NextFields,L"BUTTON",L"&Next fields",WS_TABSTOP|BS_PUSHBUTTON);
        add(FieldPage,L"STATIC",L"",SS_LEFT);
        add(Review,L"BUTTON",L"&Review request",WS_TABSTOP|BS_PUSHBUTTON);
        add(Submit,L"BUTTON",L"&Submit reviewed",WS_TABSTOP|BS_PUSHBUTTON);
        add(Back,L"BUTTON",L"&Back",WS_TABSTOP|BS_PUSHBUTTON);
        add(Notice,L"STATIC",L"",SS_LEFT);
        api.SendMessageW(controls.at(Details),EM_SETLIMITTEXT,1048576,0);
        set_font();draw(true);api.SetFocus(controls.at(Navigator));
    }
    int scale(int value) const {return MulDiv(value,static_cast<int>(dpi),96);}
    void set_font() {
        NONCLIENTMETRICSW metrics={};metrics.cbSize=sizeof(metrics);
        if(!api.SystemParametersInfoW(SPI_GETNONCLIENTMETRICS,sizeof(metrics),&metrics,0))throw Failure("gui_font_unavailable");
        HFONT next=api.CreateFontIndirectW(&metrics.lfMessageFont);if(!next)throw Failure("gui_font_unavailable");
        for(const auto& c:controls)api.SendMessageW(c.second,WM_SETFONT,reinterpret_cast<WPARAM>(next),TRUE);
        if(font)api.DeleteObject(font);font=next;
    }
    void place(int id,int x,int y,int width,int height) {
        if(!api.MoveWindow(controls.at(id),scale(x),scale(y),scale((std::max)(width,1)),scale((std::max)(height,1)),TRUE))throw Failure("gui_layout_error");
    }
    void layout() {
        if(controls.empty())return;
        RECT area={};if(!api.GetClientRect(window,&area))throw Failure("gui_layout_error");
        const int w=MulDiv(area.right,96,static_cast<int>(dpi)),h=MulDiv(area.bottom,96,static_cast<int>(dpi));
        place(Targets,10,10,85,28);place(Commands,103,10,100,28);place(Refresh,211,10,115,28);place(Clear,334,10,135,28);
        const int left=(std::min)(280,(std::max)(220,w/3)),right=left+22;
        place(Heading,10,48,left,22);place(Navigator,10,72,left,(std::max)(60,h-158));place(Open,10,h-78,left,28);
        place(Summary,right,48,w-right-10,44);place(Details,right,96,w-right-10,(std::max)(50,h-(fields.size()>2?334:302)));
        place(PreviousFields,right,h-230,130,24);place(NextFields,right+138,h-230,110,24);place(FieldPage,right+256,h-228,w-right-266,24);
        for(int i=0;i<2;++i) {place(Label0+i,right,h-194+i*46,w-right-10,20);place(Field0+i,right,h-174+i*46,w-right-10,24);}
        place(Review,right,h-88,130,28);place(Submit,right+138,h-88,140,28);place(Back,right+286,h-88,70,28);
        place(Notice,10,h-44,w-20,36);
    }
    void set(int id,const std::string& value) {
        if(!api.SetWindowTextW(controls.at(id),wide(value).c_str()))throw Failure("gui_text_error");
    }
    std::wstring get(int id) {
        const auto handle=controls.at(id);const int length=api.GetWindowTextLengthW(handle);
        if(length>4097)throw Failure("gui_field_limit");
        std::wstring value(static_cast<std::size_t>(length)+1,L'\0');
        const auto copied=api.GetWindowTextW(handle,&value[0],length+1);value.resize(static_cast<std::size_t>(copied));return value;
    }
    int measure(const std::wstring& value) {
        const auto control=controls.at(Navigator);HDC dc=api.GetDC(control);if(!dc)throw Failure("gui_font_measure");
        const auto old=api.SelectObject(dc,font);SIZE size={};
        const bool ok=api.GetTextExtentPoint32W(dc,value.c_str(),static_cast<int>(value.size()),&size)!=FALSE;
        api.SelectObject(dc,old);api.ReleaseDC(control,dc);
        if(!ok)throw Failure("gui_font_measure");return size.cx+scale(12);
    }
    void draw(bool full) {
        updating=true;
        const auto state=model->state();
        if(full) {
            const auto rows=model->rows();ids.clear();api.SendMessageW(controls.at(Navigator),LB_RESETCONTENT,0,0);
            int selected=-1,index=0,width=0;
            for(const auto& row:rows.items) {
                const auto id=row.find("id")->text;ids.push_back(id);
                const auto line=wide(id+" ["+row.find("state")->text+"]");
                const auto added=api.SendMessageW(controls.at(Navigator),LB_ADDSTRING,0,reinterpret_cast<LPARAM>(line.c_str()));
                if(added==LB_ERR || added==LB_ERRSPACE)throw Failure("gui_list_limit");
                width=(std::max)(width,measure(line));
                if(id==state.find("focus")->text)selected=index;++index;
            }
            api.SendMessageW(controls.at(Navigator),LB_SETCURSEL,static_cast<WPARAM>(selected),0);
            api.SendMessageW(controls.at(Navigator),LB_SETHORIZONTALEXTENT,width,0);
            fields.clear();for(const auto& field:state.find("fields")->items)fields.push_back(field.text);
            if(field_page*2>=fields.size())field_page=0;
            const bool paged=state.find("form")->boolean && fields.size()>2;
            for(const auto id:{PreviousFields,NextFields,FieldPage})api.ShowWindow(controls.at(id),paged?SW_SHOW:SW_HIDE);
            api.EnableWindow(controls.at(PreviousFields),field_page>0);api.EnableWindow(controls.at(NextFields),(field_page+1)*2<fields.size());
            set(FieldPage,"Fields "+std::to_string(field_page*2+1)+"-"+std::to_string((std::min)(field_page*2+2,fields.size()))+" / "+std::to_string(fields.size()));
            for(int i=0;i<2;++i) {
                const auto field_index=field_page*2+static_cast<std::size_t>(i);
                const bool visible=state.find("form")->boolean && field_index<fields.size();
                api.ShowWindow(controls.at(Label0+i),visible?SW_SHOW:SW_HIDE);api.ShowWindow(controls.at(Field0+i),visible?SW_SHOW:SW_HIDE);
                if(visible) {set(Label0+i,"&"+std::to_string(i+1)+" "+fields[field_index]);set(Field0+i,state.find("parameters")->find(fields[field_index])->text);}
            }
        }
        set(Summary,"Current: cached fake observations | Proposed: none\r\nSelection: "+presentation_json(state.find("selection")?*state.find("selection"):Value{}));
        set(Details,model->detail_text());
        set(Notice,state.find("notice")->text+" | High contrast: "+(contrast_known?(high_contrast?"on":"off"):"unknown"));
        api.EnableWindow(controls.at(Review),state.find("form")->boolean);
        api.EnableWindow(controls.at(Submit),state.find("reviewed")->boolean);
        api.EnableWindow(controls.at(Back),state.find("form")->boolean);
        updating=false;layout();
    }
    void command(int id,int notification) {
        if(updating)return;
        if(id==Navigator && notification==LBN_SELCHANGE) {
            const auto index=api.SendMessageW(controls.at(Navigator),LB_GETCURSEL,0,0);
            if(index>=0 && static_cast<std::size_t>(index)<ids.size())model->focus(ids[static_cast<std::size_t>(index)]);return;
        }
        if((id==Field0 || id==Field1) && notification==EN_CHANGE) {
            const auto index=field_page*2+static_cast<std::size_t>(id-Field0);if(index<fields.size())model->edit(fields[index],utf8(get(id)));
            draw(false);return;
        }
        if(notification!=BN_CLICKED && !(id==Navigator && notification==LBN_DBLCLK))return;
        switch(id) {
        case PreviousFields:if(field_page)--field_page;break;
        case NextFields:if((field_page+1)*2<fields.size())++field_page;break;
        case Targets:model->navigate(false);break;case Commands:model->navigate(true);break;
        case Refresh:model->refresh();break;case Clear:model->clear();break;
        case Open:case Navigator:field_page=0;model->open();break;case Review:model->review();break;
        case Submit:model->submit();break;case Back:model->back();break;
        case IDCANCEL:api.DestroyWindow(window);return;
        default:return; // IDOK/Enter never acts as an implicit submit.
        }
        draw(true);
    }
    static LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp) noexcept {
        auto& self=*current;self.window=hwnd;
        try {
            switch(message) {
            case WM_CREATE:self.dpi=self.api.GetDpiForWindow?self.api.GetDpiForWindow(hwnd):96;if(!self.dpi)self.dpi=96;self.create_controls();return 0;
            case WM_SIZE:if(wp!=SIZE_MINIMIZED)self.layout();return 0;
            case WM_GETMINMAXINFO: {
                auto* limits=reinterpret_cast<MINMAXINFO*>(lp);limits->ptMinTrackSize={self.scale(800),self.scale(570)};return 0;
            }
            case WM_COMMAND:self.command(LOWORD(wp),HIWORD(wp));return 0;
            case WM_TIMER:if(wp==1 && self.model->tick())self.draw(false);return 0;
            case WM_SETTINGCHANGE:self.read_contrast();self.set_font();self.draw(false);return 0;
            case WM_SYSCOLORCHANGE:self.api.InvalidateRect(hwnd,nullptr,TRUE);return 0;
            case WM_CTLCOLORSTATIC:case WM_CTLCOLOREDIT:case WM_CTLCOLORLISTBOX: {
                const bool canvas=reinterpret_cast<HWND>(lp)==self.controls.at(Details) || message==WM_CTLCOLOREDIT || message==WM_CTLCOLORLISTBOX;
                const int back=canvas?COLOR_WINDOW:COLOR_BTNFACE,fore=canvas?COLOR_WINDOWTEXT:COLOR_BTNTEXT;
                self.api.SetTextColor(reinterpret_cast<HDC>(wp),self.api.GetSysColor(fore));
                self.api.SetBkColor(reinterpret_cast<HDC>(wp),self.api.GetSysColor(back));
                return reinterpret_cast<LRESULT>(self.api.GetSysColorBrush(back));
            }
            case WM_CLOSE:self.api.DestroyWindow(hwnd);return 0;
            case WM_DESTROY:self.api.KillTimer(hwnd,1);self.api.PostQuitMessage(0);return 0;
            }
            return self.api.DefWindowProcW(hwnd,message,wp,lp);
        } catch(...) {self.failed=true;if(message!=WM_DESTROY)self.api.DestroyWindow(hwnd);return 0;}
    }
    int run() {
        current=this;WNDCLASSW wc={};wc.lpfnWndProc=procedure;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=class_name;
        wc.hCursor=api.LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));wc.hIcon=api.LoadIconW(nullptr,MAKEINTRESOURCEW(32512));
        wc.hbrBackground=api.GetSysColorBrush(COLOR_BTNFACE);
        if(!api.RegisterClassW(&wc))throw Failure("gui_class_registration");registered=true;
        window=api.CreateWindowExW(WS_EX_CONTROLPARENT,class_name,L"DiskEd - Image and fake storage workbench",WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT,CW_USEDEFAULT,1000,720,nullptr,nullptr,wc.hInstance,nullptr);
        if(!window || failed)throw Failure("gui_window_creation");
        if(!api.SetTimer(window,1,50,nullptr))throw Failure("gui_timer_unavailable");
        STARTUPINFOW start={};start.cb=sizeof(start);GetStartupInfoW(&start);
        api.ShowWindow(window,(start.dwFlags&STARTF_USESHOWWINDOW)?start.wShowWindow:SW_SHOWNORMAL);api.UpdateWindow(window);
        MSG message={};BOOL received=0;
        while((received=api.GetMessageW(&message,nullptr,0,0))>0) {
            if(message.message==WM_KEYDOWN && message.wParam==VK_TAB) {
                // Native multiline edits request Tab themselves. This workbench
                // reserves Tab for complete dialog traversal in every control.
                const auto next=api.GetNextDlgTabItem(window,api.GetFocus(),api.GetKeyState(VK_SHIFT)<0);
                if(next)api.SetFocus(next);continue;
            }
            if(message.message==WM_KEYDOWN && message.wParam==VK_RETURN && message.hwnd==controls.at(Navigator)) {
                if(!(message.lParam&(1LL<<30))) {model->open();draw(true);}continue;
            }
            if(!api.IsDialogMessageW(window,&message)) {api.TranslateMessage(&message);api.DispatchMessageW(&message);}
        }
        if(received<0 || failed)throw Failure("gui_event_error");return 0;
    }
};
}
int run_windows_gui(const std::function<std::unique_ptr<GuiModel>(const Value&)>& create) {
    try {Api api;Window window(api);const auto observations=window.observe();window.model=create(observations);return window.run();}
    catch(const Failure& failure) {if(_fileno(stderr)<0)return 4;std::fprintf(stderr,"disked: %s\n",failure.what());return failure.code;}
}
}
