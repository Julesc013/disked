// Private read-only UI Automation observer for an owned MMC process/desktop.
// No input injection, storage actions, registration or device-path access.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <ole2.h>
#include <UIAutomation.h>
#include <sddl.h>
#include <userenv.h>
#include <shlobj.h>
#include "runtime/command/json.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using V=disked::json::Value;
namespace {
void require(bool ok) { if(!ok) throw std::runtime_error("UI observer invariant"); }
template<class T> struct Com {
    T* p=nullptr; ~Com(){if(p)p->Release();}
    Com()=default;Com(const Com&)=delete;Com& operator=(const Com&)=delete;
};
V number(unsigned long long value){return V::number(std::to_string(value));}
std::string utf8(const wchar_t* text,int length) {
    if(!length)return {};
    const int count=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text,length,nullptr,0,nullptr,nullptr);
    if(!count)return "<invalid UTF-16>";
    std::string result(static_cast<std::size_t>(count),'\0');
    require(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text,length,&result[0],count,nullptr,nullptr)==count);
    return result;
}
std::string object_name(HANDLE handle) {
    wchar_t text[256]{};DWORD needed=0;
    require(GetUserObjectInformationW(handle,UOI_NAME,text,sizeof(text),&needed)!=FALSE);
    return utf8(text,static_cast<int>(wcslen(text)));
}
V identity() {
    HANDLE token=nullptr;require(OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)!=FALSE);
    V result=V::object();DWORD bytes=0;
    try {
        GetTokenInformation(token,TokenUser,nullptr,0,&bytes);require(bytes>0&&bytes<=16384);
        std::vector<unsigned char> data(bytes);require(GetTokenInformation(token,TokenUser,data.data(),bytes,&bytes)!=FALSE);
        wchar_t* sid=nullptr;require(ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(data.data())->User.Sid,&sid)!=FALSE);
        result.put("sid",V::string(utf8(sid,static_cast<int>(wcslen(sid)))));LocalFree(sid);
        TOKEN_ELEVATION elevated{};require(GetTokenInformation(token,TokenElevation,&elevated,sizeof(elevated),&bytes)!=FALSE);
        DWORD appcontainer=0;require(GetTokenInformation(token,TokenIsAppContainer,&appcontainer,sizeof(appcontainer),&bytes)!=FALSE);
        SID_IDENTIFIER_AUTHORITY nt=SECURITY_NT_AUTHORITY;PSID admin=nullptr;BOOL member=FALSE;
        require(AllocateAndInitializeSid(&nt,2,SECURITY_BUILTIN_DOMAIN_RID,DOMAIN_ALIAS_RID_ADMINS,0,0,0,0,0,0,&admin)!=FALSE);
        const BOOL checked=CheckTokenMembership(nullptr,admin,&member);FreeSid(admin);require(checked!=FALSE);
        result.put("administrator",V::boolean_value(member!=FALSE));
        result.put("elevated",V::boolean_value(elevated.TokenIsElevated!=0));
        result.put("restricted",V::boolean_value(IsTokenRestricted(token)!=FALSE));
        result.put("appcontainer",V::boolean_value(appcontainer!=0));
        DWORD session=0;require(ProcessIdToSessionId(GetCurrentProcessId(),&session)!=FALSE);
        result.put("session",number(session));result.put("pid",number(GetCurrentProcessId()));
        result.put("station",V::string(object_name(GetProcessWindowStation())));
        result.put("desktop",V::string(object_name(GetThreadDesktop(GetCurrentThreadId()))));
        result.put("ui_language",number(GetUserDefaultUILanguage()));
        wchar_t path[32768]{};DWORD capacity=32768;
        require(GetUserProfileDirectoryW(token,path,&capacity)!=FALSE);
        result.put("profile",V::string(utf8(path,static_cast<int>(wcslen(path)))));
        const DWORD temporary=GetTempPathW(32768,path);require(temporary>0&&temporary<32768);
        result.put("temp",V::string(utf8(path,static_cast<int>(temporary))));
        for(const auto& item:std::vector<std::pair<const char*,const KNOWNFOLDERID*>>{{"local",&FOLDERID_LocalAppData},{"roaming",&FOLDERID_RoamingAppData}}) {
            wchar_t* folder=nullptr;require(SUCCEEDED(SHGetKnownFolderPath(*item.second,0,nullptr,&folder)));
            result.put(item.first,V::string(utf8(folder,static_cast<int>(wcslen(folder)))));CoTaskMemFree(folder);
        }
    }catch(...){CloseHandle(token);throw;}
    CloseHandle(token);return result;
}
struct Windows {DWORD pid;std::vector<HWND> values;};
BOOL CALLBACK collect(HWND window,LPARAM parameter) {
    auto& state=*reinterpret_cast<Windows*>(parameter);DWORD pid=0;GetWindowThreadProcessId(window,&pid);
    if(pid==state.pid&&IsWindowVisible(window)) {
        if(state.values.size()>=16)return FALSE;
        state.values.push_back(window);
    }
    return TRUE;
}
struct Tree {
    IUIAutomation* automation;Com<IUIAutomationTreeWalker> walker;
    V rows=V::array();std::size_t text_left=131072;bool truncated=false,target=false;
    std::string disk_label;ULONGLONG deadline;
    explicit Tree(IUIAutomation* value,std::string label):automation(value),disk_label(std::move(label)),deadline(GetTickCount64()+15000) {
        require(SUCCEEDED(automation->get_RawViewWalker(&walker.p)));
    }
    V text(HRESULT status,BSTR value,bool locator=false) {
        V result=V::object();result.put("hresult",number(static_cast<unsigned long>(status)));
        const UINT length=value?SysStringLen(value):0;
        if(SUCCEEDED(status)) {
            UINT take=std::min<UINT>(length,2048);
            if(take<length&&take&&value[take-1]>=0xd800&&value[take-1]<=0xdbff)--take;
            std::string str=utf8(value,static_cast<int>(take));
            if(str=="<invalid UTF-16>")truncated=true;
            if(str.size()>text_left){str.clear();truncated=true;}
            text_left-=str.size();if(take<length)truncated=true;
            std::size_t where=str.find(disk_label);
            if(locator&&where!=std::string::npos) {
                const std::size_t after=where+disk_label.size();
                if(after==str.size()||str[after]<'0'||str[after]>'9')target=true;
            }
            result.put("value",V::string(str));result.put("utf16_units",number(length));
        }
        if(value)SysFreeString(value);return result;
    }
    void walk(IUIAutomationElement* element,unsigned depth,unsigned long long parent) {
        if(rows.items.size()>=2048||depth>20||GetTickCount64()>deadline){truncated=true;return;}
        const auto index=static_cast<unsigned long long>(rows.items.size());V row=V::object();
        row.put("index",number(index));row.put("parent",number(parent));row.put("depth",number(depth));
        BSTR str=nullptr;HRESULT status=element->get_CurrentName(&str);row.put("name",text(status,str,true));
        str=nullptr;status=element->get_CurrentClassName(&str);row.put("class",text(status,str));
        str=nullptr;status=element->get_CurrentAutomationId(&str);row.put("automation_id",text(status,str));
        CONTROLTYPEID type=0;status=element->get_CurrentControlType(&type);
        row.put("control_type_hresult",number(static_cast<unsigned long>(status)));if(SUCCEEDED(status))row.put("control_type",number(static_cast<unsigned long>(type)));
        BOOL enabled=FALSE,offscreen=TRUE;status=element->get_CurrentIsEnabled(&enabled);
        if(SUCCEEDED(status))row.put("enabled",V::boolean_value(enabled!=FALSE));
        status=element->get_CurrentIsOffscreen(&offscreen);if(SUCCEEDED(status))row.put("offscreen",V::boolean_value(offscreen!=FALSE));
        Com<IUIAutomationLegacyIAccessiblePattern> legacy;
        status=element->GetCurrentPatternAs(UIA_LegacyIAccessiblePatternId,__uuidof(IUIAutomationLegacyIAccessiblePattern),reinterpret_cast<void**>(&legacy.p));
        row.put("legacy_hresult",number(static_cast<unsigned long>(status)));
        if(SUCCEEDED(status)&&legacy.p) {
            str=nullptr;status=legacy.p->get_CurrentName(&str);row.put("legacy_name",text(status,str,true));
            str=nullptr;status=legacy.p->get_CurrentValue(&str);row.put("legacy_value",text(status,str));
            str=nullptr;status=legacy.p->get_CurrentDescription(&str);row.put("legacy_description",text(status,str));
        }
        rows.items.push_back(std::move(row));
        Com<IUIAutomationElement> child;status=walker.p->GetFirstChildElement(element,&child.p);
        while(SUCCEEDED(status)&&child.p&&!truncated) {
            walk(child.p,depth+1,index);Com<IUIAutomationElement> next;
            status=walker.p->GetNextSiblingElement(child.p,&next.p);child.p->Release();child.p=next.p;next.p=nullptr;
        }
    }
};
V capture(DWORD pid,const std::string& nonce,const std::string& label,IUIAutomation* automation) {
    V result=V::object(),attempts=V::array();const ULONGLONG deadline=GetTickCount64()+20000;
    std::string previous;unsigned stable=0;
    for(unsigned attempt=0;attempt<40&&GetTickCount64()<deadline;++attempt) {
        Windows windows{pid,{}};EnumDesktopWindows(GetThreadDesktop(GetCurrentThreadId()),collect,reinterpret_cast<LPARAM>(&windows));
        Tree tree(automation,label);V frames=V::array();if(windows.values.size()>=16)tree.truncated=true;
        for(HWND window:windows.values) {
            DWORD actual=0;GetWindowThreadProcessId(window,&actual);require(actual==pid);
            V frame=V::object();frame.put("hwnd",number(reinterpret_cast<std::uintptr_t>(window)));
            wchar_t name[256]{};GetClassNameW(window,name,256);frame.put("class",V::string(utf8(name,static_cast<int>(wcslen(name)))));
            Com<IUIAutomationElement> root;const HRESULT status=automation->ElementFromHandle(window,&root.p);
            frame.put("hresult",number(static_cast<unsigned long>(status)));
            if(SUCCEEDED(status)&&root.p)tree.walk(root.p,0,~0ULL);
            frames.items.push_back(std::move(frame));
        }
        disked::json::Limits bounds;bounds.bytes=1048576;bounds.depth=64;bounds.values=50000;bounds.string_bytes=16384;
        const std::string signature=disked::json::dump(tree.rows,bounds)+disked::json::dump(frames,bounds);
        stable=tree.target?(signature==previous?stable+1:1):0;previous=signature;
        V summary=V::object();summary.put("attempt",number(attempt));summary.put("windows",number(windows.values.size()));summary.put("stable_snapshots",number(stable));
        summary.put("nodes",number(tree.rows.items.size()));summary.put("target_seen",V::boolean_value(tree.target));attempts.items.push_back(std::move(summary));
        result.put("frames",std::move(frames));result.put("nodes",std::move(tree.rows));
        result.put("target_label_seen",V::boolean_value(tree.target));result.put("truncated",V::boolean_value(tree.truncated));
        result.put("stable_snapshots",number(stable));
        if(stable>=2||tree.truncated||attempt==39||GetTickCount64()+500>=deadline)break;
        Sleep(500);
    }
    result.put("attempts",std::move(attempts));result.put("mmc_pid",number(pid));result.put("nonce",V::string(nonce));
    result.put("target_label",V::string(label));return result;
}
}
int main(int argc,char** argv) {
    try {
        require(argc==2||argc==4);V output=V::object();
        const HRESULT initialized=CoInitializeEx(nullptr,COINIT_MULTITHREADED);require(SUCCEEDED(initialized));
        try {
            output.put("identity",identity());
            Com<IUIAutomation> automation;const HRESULT created=CoCreateInstance(CLSID_CUIAutomation,nullptr,CLSCTX_INPROC_SERVER,__uuidof(IUIAutomation),reinterpret_cast<void**>(&automation.p));
            output.put("uia_hresult",number(static_cast<unsigned long>(created)));require(SUCCEEDED(created));
            if(argc==2)require(std::string(argv[1])=="--identity");
            else {
                const std::string pid_text=argv[1],nonce=argv[2],label=argv[3];
                require(disked::json::decimal_u64(pid_text)&&std::stoull(pid_text)>0&&std::stoull(pid_text)<=MAXDWORD);
                require(nonce.size()==32&&label.size()<=32&&label.find("Disk ")==0);
                output.put("capture",capture(static_cast<DWORD>(std::stoull(pid_text)),nonce,label,automation.p));
            }
        }catch(...){CoUninitialize();throw;}
        CoUninitialize();disked::json::Limits limits;limits.bytes=1048576;limits.depth=64;limits.values=50000;limits.string_bytes=16384;
        std::cout<<disked::json::dump(output,limits)<<'\n';return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 2;}
}
