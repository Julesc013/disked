#include "platform/windows/ui/window_capture.h"
#include "portable/hash/sha256.h"
#include "runtime/command/json.h"
#include <sddl.h>
#include <algorithm>
#include <cstdio>
#include <iostream>
#include <stdexcept>

using V=disked::json::Value;
using Request=disked::ui::WindowCaptureRequest;
using Result=disked::ui::WindowCaptureResult;
using Status=disked::ui::WindowCaptureStatus;
static void require(bool value){if(!value)throw std::runtime_error("cooperative capture invariant");}
static V number(std::uint64_t n){return V::string(std::to_string(n));}
static const V& field(const V& v,const char* key){const auto* p=v.find(key);require(p!=nullptr);return *p;}
static std::string text(const V& v,const char* key){const auto& x=field(v,key);require(x.kind==V::Kind::string&&x.text.size()<=255);return x.text;}
static std::uint64_t integer(const std::string& s){require(!s.empty()&&s.size()<=20&&s.find_first_not_of("0123456789")==s.npos);std::size_t n=0;const auto v=std::stoull(s,&n);require(n==s.size());return v;}
static std::wstring wide(const std::string& s){require(s.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-\\") == s.npos);return {s.begin(),s.end()};}
static std::vector<unsigned char> unhex(const std::string& s){
    require(s.size()%2==0);std::vector<unsigned char> out;
    for(std::size_t i=0;i<s.size();i+=2){unsigned value=0;for(auto c:s.substr(i,2)){value<<=4;if(c>='0'&&c<='9')value+=c-'0';else if(c>='a'&&c<='f')value+=10+c-'a';else require(false);}out.push_back(static_cast<unsigned char>(value));}return out;
}
struct Handle{HANDLE value=nullptr;~Handle(){if(value&&value!=INVALID_HANDLE_VALUE)CloseHandle(value);}};
struct State{
    std::array<std::array<std::array<unsigned char,3>,16>,2> colors{};
    std::uint64_t nonce=0;
    unsigned phase=0,prints=0,paints=0,transition=0;
    bool blank=false,hang=false,error=false,tree=false;
    HWND first_child=nullptr;
};
struct Binding{State* state;int offset=-1;};
static void write(const void* data,std::size_t size);
static void mark(HWND window,std::uint64_t nonce){
    require(SetPropW(window,L"DiskEd.Capture.NonceLow",reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(static_cast<std::uint32_t>(nonce))))!=FALSE);
    require(SetPropW(window,L"DiskEd.Capture.NonceHigh",reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(nonce>>32)))!=FALSE);
}
static void draw(State& state,HDC dc,int offset){
    if(state.blank)return;
    if(state.tree&&offset<0){RECT box{0,0,240,96};if(!FillRect(dc,&box,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH))))state.error=true;return;}
    for(unsigned i=0;i<16;++i){const auto& rgb=state.colors[state.phase][i];const auto brush=CreateSolidBrush(RGB(rgb[0],rgb[1],rgb[2]));
        if(offset>=0&&(static_cast<int>(i%4*60)<offset||static_cast<int>(i%4*60)>=offset+120)){if(brush)DeleteObject(brush);continue;}
        const auto shift=offset<0?0:offset;
        RECT rect{static_cast<LONG>(i%4*60)-shift,static_cast<LONG>(i/4*24),static_cast<LONG>((i%4+1)*60)-shift,static_cast<LONG>((i/4+1)*24)};
        if(!brush||!FillRect(dc,&rect,brush))state.error=true;if(brush)DeleteObject(brush);
    }
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_NCCREATE){const auto* create=reinterpret_cast<CREATESTRUCTW*>(lp);SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(create->lpCreateParams));}
    auto* binding=reinterpret_cast<Binding*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(binding){auto* state=binding->state;
        if(message==WM_PAINT){PAINTSTRUCT paint{};const auto dc=BeginPaint(window,&paint);if(dc){++state->paints;draw(*state,dc,binding->offset);EndPaint(window,&paint);}else state->error=true;return 0;}
        if(message==WM_PRINTCLIENT){++state->prints;if(state->hang){
                const auto ready=disked::json::dump(V::object().put("schema",V::string("org.disked.cooperative-capture-ready/1")).put("pid",number(GetCurrentProcessId())).put("nonce",number(state->nonce)).put("holding_job_query",V::boolean_value(true)))+"\n";
                write(ready.data(),ready.size());Sleep(INFINITE);
            }draw(*state,reinterpret_cast<HDC>(wp),binding->offset);
            if(binding->offset<0){
                if(state->transition==1){try{mark(window,state->nonce+1);}catch(...){state->error=true;}}
                if(state->transition==2&&!SetWindowPos(window,nullptr,0,0,241,96,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE))state->error=true;
                if(state->transition==3&&!SetWindowPos(state->first_child,nullptr,0,0,119,96,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE))state->error=true;
                if(state->transition==4)ShowWindow(state->first_child,SW_HIDE);
            }
            return 0;
        }
        if(message==WM_ERASEBKGND)return 1;
    }
    return DefWindowProcW(window,message,wp,lp);
}
struct Windows{
    HINSTANCE instance=GetModuleHandleW(nullptr);HWND first=nullptr,other=nullptr;bool registered=false;DPI_AWARENESS_CONTEXT dpi=nullptr;
    ~Windows(){if(other)DestroyWindow(other);if(first){RemovePropW(first,L"DiskEd.Capture.NonceLow");RemovePropW(first,L"DiskEd.Capture.NonceHigh");DestroyWindow(first);}if(registered)UnregisterClassW(L"DiskEdCooperativeCaptureControl",instance);if(dpi)SetThreadDpiAwarenessContext(dpi);}
};
struct ThreadCall{const Request* request;Status status=Status::captured;bool empty=false;};
static DWORD WINAPI foreign_thread(void* raw){auto& value=*static_cast<ThreadCall*>(raw);try{auto result=disked::ui::capture_owned_window_client(*value.request);value.status=result.status;value.empty=result.bgra.empty();}catch(...){value.empty=false;}return 0;}
struct ForeignChild{HWND parent=nullptr,window=nullptr;Binding binding;HANDLE ready=nullptr,finish=nullptr;DWORD error=0;};
static DWORD WINAPI foreign_child(void* raw){auto& value=*static_cast<ForeignChild*>(raw);
    value.window=CreateWindowExW(WS_EX_NOPARENTNOTIFY,L"DiskEdCooperativeCaptureControl",L"Foreign-thread owned child",WS_CHILD,0,0,1,1,value.parent,nullptr,GetModuleHandleW(nullptr),&value.binding);
    if(!value.window)value.error=GetLastError();SetEvent(value.ready);WaitForSingleObject(value.finish,2000);
    if(value.window)DestroyWindow(value.window);return 0;
}
static bool pump_wait(HANDLE handle){const auto start=GetTickCount64();while(GetTickCount64()-start<1800){
    if(WaitForSingleObject(handle,0)==WAIT_OBJECT_0)return true;
    MSG message{};while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessageW(&message);}
    MsgWaitForMultipleObjects(1,&handle,FALSE,10,QS_ALLINPUT);
}return false;}
static V identity(){
    Handle token;require(OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token.value)!=FALSE);
    std::vector<unsigned char> data(16384);DWORD used=0;require(GetTokenInformation(token.value,TokenUser,data.data(),static_cast<DWORD>(data.size()),&used)!=FALSE);
    char* sid=nullptr;require(ConvertSidToStringSidA(reinterpret_cast<TOKEN_USER*>(data.data())->User.Sid,&sid)!=FALSE);
    const std::string full(sid);LocalFree(sid);V out=V::object();out.put("sid",V::string(full));
    for(auto pair:{std::make_pair("elevated",TokenElevation),std::make_pair("appcontainer",TokenIsAppContainer)}){DWORD value=0;require(GetTokenInformation(token.value,pair.second,&value,sizeof(value),&used)!=FALSE);out.put(pair.first,V::boolean_value(value!=0));}
    require(GetTokenInformation(token.value,TokenIntegrityLevel,data.data(),static_cast<DWORD>(data.size()),&used)!=FALSE);
    sid=nullptr;require(ConvertSidToStringSidA(reinterpret_cast<TOKEN_MANDATORY_LABEL*>(data.data())->Label.Sid,&sid)!=FALSE);
    const std::string integrity(sid);LocalFree(sid);out.put("integrity_sid",V::string(integrity));
    return out.put("restricted",V::boolean_value(IsTokenRestricted(token.value)!=FALSE));
}
static void write(const void* data,std::size_t size){const auto* p=static_cast<const unsigned char*>(data);while(size){DWORD done=0;require(WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),p,static_cast<DWORD>(size),&done,nullptr)&&done);p+=done;size-=done;}}
int main(int argc,char** argv){
    const char* stage="input";
    try{
        const std::string mode=argc==1?"normal":argc==2?argv[1]:"invalid";
        if(mode!="normal"&&mode!="--blank"&&mode!="--hang"&&mode!="--tree"){std::fputs("invalid_control_mode\n",stderr);return 2;}
        std::string line;require(static_cast<bool>(std::getline(std::cin,line))&&line.size()<=4096);
        disked::json::Limits limits;limits.bytes=4096;limits.values=128;limits.string_bytes=255;const auto input=disked::json::parse(line,limits);require(input.fields.size()==7);
        const auto seed=unhex(text(input,"challenge"));require(seed.size()==16);
        State state;state.nonce=integer(text(input,"nonce"));require(static_cast<std::uint32_t>(state.nonce)&&static_cast<std::uint32_t>(state.nonce>>32));
        state.blank=mode=="--blank";state.hang=mode=="--hang";state.tree=mode=="--tree";
        Binding root_binding{&state,-1},left_binding{&state,0},right_binding{&state,120};
        for(unsigned p=0;p<2;++p)for(unsigned i=0;i<16;++i){std::string bytes("DiskEd pixel-origin/1");bytes.push_back('\0');bytes.append(seed.begin(),seed.end());bytes.push_back(static_cast<char>(p));bytes.push_back(static_cast<char>(i));
            std::array<unsigned char,32> sum{};disked::sha256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),sum.data());std::copy_n(sum.begin(),3,state.colors[p][i].begin());}
        stage="job_transfer";Handle job,wrong;job.value=reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(integer(text(input,"job_handle"))));wrong.value=reinterpret_cast<HANDLE>(static_cast<ULONG_PTR>(integer(text(input,"wrong_job_handle"))));require(job.value&&wrong.value&&job.value!=wrong.value);
        stage="job_rights";
        V job_refusals=V::array();for(auto access:{JOB_OBJECT_ASSIGN_PROCESS,JOB_OBJECT_SET_ATTRIBUTES,JOB_OBJECT_TERMINATE}){SetLastError(0);HANDLE handle=nullptr;const auto opened=DuplicateHandle(GetCurrentProcess(),job.value,GetCurrentProcess(),&handle,access,FALSE,0);const auto error=GetLastError();if(handle)CloseHandle(handle);if(opened||error!=ERROR_ACCESS_DENIED)throw std::runtime_error("job_access="+std::to_string(access)+":opened="+std::to_string(opened!=FALSE)+":error="+std::to_string(error));job_refusals.items.push_back(V::object().put("access",number(access)).put("error",number(error)));}
        stage="dpi";Windows windows;windows.dpi=SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);require(windows.dpi!=nullptr);
        WNDCLASSEXW definition{};definition.cbSize=sizeof(definition);definition.lpfnWndProc=procedure;definition.hInstance=windows.instance;definition.lpszClassName=L"DiskEdCooperativeCaptureControl";
        stage="register_class";require(RegisterClassExW(&definition)!=0);windows.registered=true;
        stage="window_create";
        windows.first=CreateWindowExW(0,definition.lpszClassName,L"Owned capture control",WS_POPUP|WS_VISIBLE,0,0,240,96,nullptr,nullptr,windows.instance,&root_binding);require(windows.first!=nullptr);mark(windows.first,state.nonce);
        windows.other=CreateWindowExW(0,definition.lpszClassName,L"Wrong owned control",WS_POPUP,0,0,240,96,nullptr,nullptr,windows.instance,&root_binding);require(windows.other!=nullptr);
        if(state.tree){state.first_child=CreateWindowExW(0,definition.lpszClassName,L"Left tiles",WS_CHILD|WS_VISIBLE,0,0,120,96,windows.first,nullptr,windows.instance,&left_binding);
            require(state.first_child&&CreateWindowExW(0,definition.lpszClassName,L"Right tiles",WS_CHILD|WS_VISIBLE,120,0,120,96,windows.first,nullptr,windows.instance,&right_binding));}
        Request request;request.window=windows.first;request.process=GetCurrentProcessId();request.thread=GetCurrentThreadId();request.job=job.value;request.desktop=wide(text(input,"desktop"));request.nonce=state.nonce;
        request.image_volume=integer(text(input,"volume"));const auto id=unhex(text(input,"file_id"));require(id.size()==16);std::copy(id.begin(),id.end(),request.image_file_id.begin());request.width=240;request.height=96;request.child_tree=state.tree;
        stage="scope_refusals";V negative=V::array();
        auto refused=[&](const char* name,const Request& bad,Status wanted){const auto before=state.prints;auto captured=disked::ui::capture_owned_window_client(bad);if(captured.status!=wanted||!captured.bgra.empty()||state.prints!=before)throw std::runtime_error(std::string(name)+":capture_status="+std::to_string(static_cast<int>(captured.status)));negative.items.push_back(V::object().put("name",V::string(name)).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(false)));};
        auto bad=request;++bad.process;refused("wrong_process",bad,Status::identity_mismatch);
        bad=request;++bad.thread;refused("wrong_thread",bad,Status::identity_mismatch);
        bad=request;++bad.nonce;refused("wrong_nonce",bad,Status::identity_mismatch);
        bad=request;bad.desktop+=L"-wrong";refused("wrong_desktop",bad,Status::identity_mismatch);
        bad=request;bad.image_file_id[0]^=1;refused("wrong_image",bad,Status::identity_mismatch);
        bad=request;bad.job=wrong.value;refused("wrong_job",bad,Status::identity_mismatch);
        bad=request;--bad.width;refused("wrong_geometry",bad,Status::geometry_changed);
        bad=request;bad.window=windows.other;refused("wrong_window",bad,Status::identity_mismatch);
        stage="foreign_thread";ThreadCall threaded{&request};Handle thread;thread.value=CreateThread(nullptr,0,foreign_thread,&threaded,0,nullptr);require(thread.value&&WaitForSingleObject(thread.value,2000)==WAIT_OBJECT_0&&threaded.status==Status::identity_mismatch&&threaded.empty);
        negative.items.push_back(V::object().put("name",V::string("foreign_thread")).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(false)));
        for(unsigned change=1;change<=2;++change){stage=change==1?"epoch_transition":"geometry_transition";state.transition=change;auto failed=disked::ui::capture_owned_window_client(request);if(!failed.bgra.empty()||failed.status!=(change==1?Status::identity_mismatch:Status::geometry_changed))throw std::runtime_error("transition capture_status="+std::to_string(static_cast<int>(failed.status)));state.transition=0;mark(windows.first,state.nonce);require(SetWindowPos(windows.first,nullptr,0,0,240,96,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE)!=FALSE);
            negative.items.push_back(V::object().put("name",V::string(change==1?"epoch_during_capture":"geometry_during_capture")).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(true)));}
        V tree_controls=V::array();
        if(state.tree){
            stage="foreign_child_thread";Handle ready,finish,foreign;ready.value=CreateEventW(nullptr,TRUE,FALSE,nullptr);finish.value=CreateEventW(nullptr,TRUE,FALSE,nullptr);require(ready.value&&finish.value);
            ForeignChild data{windows.first,nullptr,Binding{&state,-1},ready.value,finish.value,0};foreign.value=CreateThread(nullptr,0,foreign_child,&data,0,nullptr);
            require(foreign.value&&pump_wait(ready.value)&&data.window&&data.error==0);const auto before=state.prints;auto failed=disked::ui::capture_owned_window_client(request);
            const bool foreign_ok=failed.status==Status::identity_mismatch&&failed.bgra.empty()&&state.prints==before;SetEvent(finish.value);require(pump_wait(foreign.value)&&foreign_ok);
            tree_controls.items.push_back(V::object().put("name",V::string("foreign_child_thread")).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(false)));
            stage="child_count_limit";std::vector<HWND> extras;for(unsigned i=0;i<63;++i){const auto child=CreateWindowExW(0,L"STATIC",L"bounded extra",WS_CHILD,0,0,1,1,windows.first,nullptr,windows.instance,nullptr);require(child!=nullptr);extras.push_back(child);}
            const auto prints=state.prints;failed=disked::ui::capture_owned_window_client(request);const bool count_ok=failed.status==Status::invalid_request&&failed.bgra.empty()&&state.prints==prints;
            for(auto child:extras)require(DestroyWindow(child)!=FALSE);require(count_ok);
            tree_controls.items.push_back(V::object().put("name",V::string("child_count_limit")).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(false)));
            for(unsigned change=3;change<=4;++change){stage=change==3?"child_geometry":"child_visibility";state.transition=change;failed=disked::ui::capture_owned_window_client(request);state.transition=0;
                require(failed.status==Status::geometry_changed&&failed.bgra.empty());require(SetWindowPos(state.first_child,nullptr,0,0,120,96,SWP_NOMOVE|SWP_NOZORDER|SWP_NOACTIVATE)!=FALSE);ShowWindow(state.first_child,SW_SHOWNOACTIVATE);
                tree_controls.items.push_back(V::object().put("name",V::string(change==3?"child_geometry_during_capture":"child_visibility_during_capture")).put("refused",V::boolean_value(true)).put("render_called",V::boolean_value(true)));}
        }
        stage="positive_capture";V phases=V::array();std::vector<unsigned char> pixels;
        for(unsigned p=0;p<2;++p){state.phase=p;require(RedrawWindow(windows.first,nullptr,nullptr,RDW_INVALIDATE|RDW_UPDATENOW|RDW_ERASE)!=FALSE);auto captured=disked::ui::capture_owned_window_client(request);
            if(state.error||captured.status!=Status::captured||captured.bgra.size()!=92160||captured.gdi_before!=captured.gdi_after||captured.descendants!=(state.tree?2u:0u))
                throw std::runtime_error("phase"+std::to_string(p)+":capture_status="+std::to_string(static_cast<int>(captured.status))+":gdi="+std::to_string(captured.gdi_before)+"/"+std::to_string(captured.gdi_after));
            phases.items.push_back(V::object().put("phase",number(p)).put("width",number(240)).put("height",number(96)).put("bytes",number(captured.bgra.size())).put("gdi_before",number(captured.gdi_before)).put("gdi_after",number(captured.gdi_after)));
            pixels.insert(pixels.end(),captured.bgra.begin(),captured.bgra.end());}
        stage="image_open_refusals";wchar_t own_image[32768]{};require(GetModuleFileNameW(nullptr,own_image,32768)!=0);V mutation=V::array();
        for(auto access:{GENERIC_WRITE,DELETE}){SetLastError(0);const auto handle=CreateFileW(own_image,access,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);const auto error=GetLastError();if(handle!=INVALID_HANDLE_VALUE)CloseHandle(handle);require(handle==INVALID_HANDLE_VALUE&&(error==ERROR_SHARING_VIOLATION||error==ERROR_ACCESS_DENIED));mutation.items.push_back(V::object().put("access",number(access)).put("error",number(error)));}
        stage="reply";V report=V::object();report.put("schema",V::string("org.disked.cooperative-capture-control/1")).put("method",V::string("owned-ui-thread-cooperative-client-control/1")).put("pid",number(request.process)).put("thread",number(request.thread)).put("window",number(reinterpret_cast<ULONG_PTR>(windows.first))).put("nonce",number(state.nonce)).put("identity",identity()).put("negative_controls",negative).put("phases",phases).put("mutating_open_refusals",mutation).put("job_access_refusals",job_refusals).put("display_dc_read",V::boolean_value(false)).put("desktop_switched",V::boolean_value(false));
        if(state.tree)report.put("schema",V::string("org.disked.cooperative-tree-control/1")).put("method",V::string("owned-ui-thread-cooperative-client-tree/1")).put("tree_controls",tree_controls).put("descendants",number(2));
        const auto header=disked::json::dump(report);require(header.size()<=16384);const auto size=static_cast<std::uint32_t>(header.size());unsigned char prefix[4];for(unsigned i=0;i<4;++i)prefix[i]=static_cast<unsigned char>(size>>(8*i));write(prefix,4);write(header.data(),header.size());write(pixels.data(),pixels.size());return 0;
    }catch(const std::exception& error){const auto observed=GetLastError();std::fprintf(stderr,"cooperative control:%s: %s (last_error_after_unwind=%lu)\n",stage,error.what(),observed);return 1;}
}
