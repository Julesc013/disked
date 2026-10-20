#include <windows.h>
#include <sddl.h>
#include <cstdio>
#include <string>
#include <vector>

static bool emit(DWORD stream, const void* data, DWORD count) {
    DWORD written=0;
    return WriteFile(GetStdHandle(stream), data, count, &written, nullptr) && written==count;
}
static int identity() {
    HANDLE token=nullptr;
    if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token))return 10;
    DWORD needed=0; GetTokenInformation(token,TokenUser,nullptr,0,&needed);
    if(!needed || needed>4096){CloseHandle(token);return 11;}
    std::vector<unsigned char> bytes(needed);
    if(!GetTokenInformation(token,TokenUser,bytes.data(),needed,&needed)){CloseHandle(token);return 12;}
    wchar_t* text=nullptr;
    if(!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(bytes.data())->User.Sid,&text)){CloseHandle(token);return 13;}
    char sid[256]{};
    if(!WideCharToMultiByte(CP_UTF8,0,text,-1,sid,sizeof(sid),nullptr,nullptr)){LocalFree(text);CloseHandle(token);return 14;}
    LocalFree(text);
    TOKEN_ELEVATION elevation{};DWORD app=1;
    if(!GetTokenInformation(token,TokenElevation,&elevation,sizeof(elevation),&needed) ||
       !GetTokenInformation(token,TokenIsAppContainer,&app,sizeof(app),&needed)){CloseHandle(token);return 15;}
    BOOL inside=FALSE; if(!IsProcessInJob(GetCurrentProcess(),nullptr,&inside)){CloseHandle(token);return 16;}
    const bool restricted=IsTokenRestricted(token)!=FALSE;CloseHandle(token);
    std::string out="{\"sid\":\""+std::string(sid)+"\",\"restricted\":"+(restricted?"true":"false")+
        ",\"elevated\":"+(elevation.TokenIsElevated?"true":"false")+",\"appcontainer\":"+(app?"true":"false")+
        ",\"in_job\":"+(inside?"true":"false")+",\"stdio\":[";
    const DWORD streams[]={STD_INPUT_HANDLE,STD_OUTPUT_HANDLE,STD_ERROR_HANDLE};
    for(unsigned i=0;i<3;i++){
        HANDLE handle=GetStdHandle(streams[i]);FILE_ID_INFO id{};
        if(GetFileType(handle)!=FILE_TYPE_DISK || !GetFileInformationByHandleEx(handle,FileIdInfo,&id,sizeof(id)))return 17;
        char volume[64]{};std::snprintf(volume,sizeof(volume),"%llu",static_cast<unsigned long long>(id.VolumeSerialNumber));
        std::string hex;const char* digits="0123456789abcdef";
        for(unsigned char c:id.FileId.Identifier){hex+=digits[c>>4];hex+=digits[c&15];}
        if(i)out+=",";
        out+="{\"volume\":\""+std::string(volume)+"\",\"identity\":\""+hex+"\"}";
    }
    out+="]}\n";
    return emit(STD_OUTPUT_HANDLE,out.data(),static_cast<DWORD>(out.size()))?0:18;
}
int wmain(int argc,wchar_t** argv){
    if(argc!=2)return 2;
    const std::wstring mode=argv[1];
    if(mode==L"identity")return identity();
    if(mode==L"echo"){
        unsigned char buffer[4096];DWORD count=0;
        while(ReadFile(GetStdHandle(STD_INPUT_HANDLE),buffer,sizeof(buffer),&count,nullptr) && count)
            if(!emit(STD_OUTPUT_HANDLE,buffer,count))return 3;
        const unsigned char error[]={0,'E','R','R',255,13,10};
        return emit(STD_ERROR_HANDLE,error,sizeof(error))?0:4;
    }
    if(mode==L"refuse"){emit(STD_OUTPUT_HANDLE,"OUT",3);emit(STD_ERROR_HANDLE,"ERR",3);return 7;}
    if(mode==L"sleep"){Sleep(30000);return 0;}
    if(mode==L"overrun"){
        unsigned char buffer[4096];for(auto& c:buffer)c='A';
        for(unsigned i=0;i<16384;i++)if(!emit(STD_OUTPUT_HANDLE,buffer,sizeof(buffer)))break;
        return 0;
    }
    if(mode==L"memory"){
        MEMORYSTATUSEX status{};status.dwLength=sizeof(status);if(!GlobalMemoryStatusEx(&status))return 20;
        SetLastError(0);void* value=VirtualAlloc(nullptr,300ull*1024*1024,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
        const DWORD error=GetLastError();if(value)VirtualFree(value,0,MEM_RELEASE);
        char out[256]{};const int n=std::snprintf(out,sizeof(out),"{\"denied\":%s,\"error\":%lu,\"available_commit_before\":%llu}\n",
            value?"false":"true",error,static_cast<unsigned long long>(status.ullAvailPageFile));
        if(n<0 || static_cast<size_t>(n)>=sizeof(out))return 21;
        emit(STD_OUTPUT_HANDLE,out,static_cast<DWORD>(n));return value?22:0;
    }
    if(mode==L"grandchild"){
        HANDLE file=CreateFileW(L"grandchild.ready",GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file==INVALID_HANDLE_VALUE)return 30;
        DWORD count=0;const bool written=WriteFile(file,"READY",5,&count,nullptr)&&count==5;
        const bool emitted=written && emit(STD_OUTPUT_HANDLE,"CHILD",5);CloseHandle(file);
        if(!emitted)return 31;
        Sleep(30000);return 0;
    }
    if(mode==L"parent"){
        if(!emit(STD_OUTPUT_HANDLE,"PARENT",6))return 32;
        wchar_t path[32768];if(!GetModuleFileNameW(nullptr,path,32768))return 33;
        std::wstring command=L"\""+std::wstring(path)+L"\" grandchild";
        STARTUPINFOW startup{};startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESTDHANDLES;
        startup.hStdInput=GetStdHandle(STD_INPUT_HANDLE);startup.hStdOutput=GetStdHandle(STD_OUTPUT_HANDLE);startup.hStdError=GetStdHandle(STD_ERROR_HANDLE);
        PROCESS_INFORMATION child{};
        if(!CreateProcessW(path,&command[0],nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,nullptr,&startup,&child))return 34;
        CloseHandle(child.hThread);CloseHandle(child.hProcess);
        for(unsigned i=0;i<100;i++){
            HANDLE ready=CreateFileW(L"grandchild.ready",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(ready!=INVALID_HANDLE_VALUE){CloseHandle(ready);Sleep(20);return 0;}
            Sleep(10);
        }
        return 35;
    }
    return 2;
}
