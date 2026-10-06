#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "invocation.h"
#include "bootstrap_registry.h"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
namespace disked {
using json::Value;
namespace {
struct Channel {Value value;std::string type;bool usable=false,console=false;};
Channel channel(DWORD id,FILE* stream) {
    Channel out;const HANDLE handle=GetStdHandle(id);DWORD mode=0;
    out.type="unknown";DWORD error=0;
    if(handle==nullptr)out.type="absent";
    else if(handle==INVALID_HANDLE_VALUE)out.type="invalid";
    else {
        SetLastError(ERROR_SUCCESS);const DWORD type=GetFileType(handle);error=GetLastError();
        if(type==FILE_TYPE_UNKNOWN && error!=ERROR_SUCCESS)out.type="invalid";
        else if(GetConsoleMode(handle,&mode)) {out.type="console";out.console=true;}
        else if(type==FILE_TYPE_PIPE)out.type="pipe";
        else if(type==FILE_TYPE_DISK)out.type="file";
        else if(type==FILE_TYPE_CHAR)out.type="character";
    }
    const int descriptor=_fileno(stream);
    // Negative CRT descriptors represent unassociated streams. Do not invoke
    // invalid-parameter handling or replace them with console/file handles.
    out.usable=descriptor>=0 && out.type!="absent" && out.type!="invalid";
    if(out.usable && _setmode(descriptor,_O_BINARY)==-1)out.usable=false;
    out.value=Value::object().put("kind",Value::string(out.type)).put("crt_usable",Value::boolean_value(out.usable))
        .put("console_mode",out.console?Value::number(std::to_string(mode)):Value{})
        .put("observation_error",error?Value::number(std::to_string(error)):Value{});
    return out;
}
}
InvocationHost observe_windows_invocation() {
    InvocationHost host;
    const auto input=channel(STD_INPUT_HANDLE,stdin),output=channel(STD_OUTPUT_HANDLE,stdout),diagnostics=channel(STD_ERROR_HANDLE,stderr);
    host.input_usable=input.usable;host.output_usable=output.usable;host.error_usable=diagnostics.usable;
    DWORD processes[64]={};const DWORD count=GetConsoleProcessList(processes,64);
    // Membership is not creator identity. Protect observed sharing; never infer
    // ownership of a lone/unknown console or permission to hide it.
    const bool shared=count>1;
    CONSOLE_SCREEN_BUFFER_INFO info={};
    const bool geometry=output.console && GetConsoleScreenBufferInfo(GetStdHandle(STD_OUTPUT_HANDLE),&info);
    DWORD pending_events=0;
    const bool console_input=input.console && GetNumberOfConsoleInputEvents(GetStdHandle(STD_INPUT_HANDLE),&pending_events);
    // GetConsoleMode alone also succeeds for a screen buffer incorrectly passed
    // as stdin. Verify channel roles without consuming any pending input.
    const bool prompt=console_input && geometry && input.usable && output.usable;
    const std::string terminal=prompt?(geometry?"capable":"limited"):"none";
    Value dimensions;
    if(geometry)dimensions=Value::object().put("buffer_columns",Value::number(std::to_string(info.dwSize.X)))
        .put("buffer_rows",Value::number(std::to_string(info.dwSize.Y)))
        .put("viewport_columns",Value::number(std::to_string(info.srWindow.Right-info.srWindow.Left+1)))
        .put("viewport_rows",Value::number(std::to_string(info.srWindow.Bottom-info.srWindow.Top+1)));
    auto channel_capability=[](const Channel& c,const char* encoding) {
        const auto kind=c.console?"terminal":c.type=="pipe"?"pipe":c.type=="file"?"file":c.type=="absent"?"absent":"unknown";
        return Value::object().put("kind",Value::string(kind)).put("encoding",Value::string(c.console?encoding:"uninspected"))
            .put("interactive",Value::string(c.console && c.usable?"yes":"no"));
    };
    auto size=[&](bool viewport) {return Value::object()
        .put("columns",geometry?Value::number(std::to_string(viewport?info.srWindow.Right-info.srWindow.Left+1:info.dwSize.X)):Value{})
        .put("rows",geometry?Value::number(std::to_string(viewport?info.srWindow.Bottom-info.srWindow.Top+1:info.dwSize.Y)):Value{});};
    auto capabilities=Value::object().put("schema",Value::string("org.disked.terminal-capabilities/1"))
        .put("source",Value::string("observed")).put("target_profile",Value::string(bootstrap::target))
        .put("backend",Value::string(prompt?"native-console":"plain"))
        .put("input",channel_capability(input,"utf-16-console-events")).put("output",channel_capability(output,"utf-16-console-api"))
        .put("diagnostics",channel_capability(diagnostics,"utf-16-console-api"))
        .put("viewport",size(true)).put("backing_buffer",size(false))
        .put("cursor_addressing",Value::string(geometry?"yes":"no")).put("colour",Value::string(geometry?"16":"unknown"))
        .put("glyphs",Value::string("ascii")).put("keyboard_events",Value::string(console_input?"yes":"no"))
        .put("mouse_events",Value::string("unknown")).put("resize_events",Value::string(console_input?"yes":"no"))
        .put("paste_detection",Value::string("unknown")).put("alternate_screen",Value::string("unknown"))
        .put("screen_owner",Value::string(shared?"caller":"unknown")).put("prefer_linear",Value::boolean_value(false))
        .put("reduce_motion",Value::boolean_value(true)).put("resource_budget_reference",Value::string("DE-026:DE-W014"))
        .put("evidence",Value::array());
    // Startup API capabilities, not a probe that reads input or activates a screen.
    capabilities.fields["input"].put("interactive",Value::string(console_input && input.usable?"yes":"no"));
    capabilities.fields["output"].put("interactive",Value::string(geometry && output.usable?"yes":"no"));
    CONSOLE_SCREEN_BUFFER_INFO diagnostic_info={};
    const bool diagnostic_output=diagnostics.console && GetConsoleScreenBufferInfo(GetStdHandle(STD_ERROR_HANDLE),&diagnostic_info);
    capabilities.fields["diagnostics"].put("interactive",Value::string(diagnostic_output && diagnostics.usable?"yes":"no"));
    host.observations=Value::object().put("stdin",input.value).put("stdout",output.value).put("stderr",diagnostics.value)
        .put("terminal",Value::string(terminal)).put("geometry",dimensions)
        .put("console_input_verified",Value::boolean_value(console_input))
        .put("console_process_count",count?Value::number(std::to_string(count)):Value{})
        .put("console_list_complete",Value::boolean_value(count>0 && count<=64))
        .put("console_ownership",Value::string(shared?"shared-protected":"unknown"))
        .put("display",Value::string("unknown")).put("desktop_activation",Value::string("unknown"))
        .put("adapter",Value::string("windows.standard-handles/1")).put("terminal_capabilities",capabilities);
    host.policy=Value::object().put("stdin",Value::string(input.type)).put("stdout",Value::string(output.type))
        .put("terminal",Value::string(terminal)).put("console_owner",Value::string(shared?"caller":"unknown"))
        .put("prompt_channel",Value::boolean_value(prompt)).put("gui_available",Value::boolean_value(false))
        .put("tui_available",Value::boolean_value(true)).put("display",Value::boolean_value(false));
    return host;
}
}
