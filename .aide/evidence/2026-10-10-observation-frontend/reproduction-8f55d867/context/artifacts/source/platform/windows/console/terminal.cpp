#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "terminal.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>

namespace disked {
namespace {
std::atomic<bool> interrupted{false};
BOOL WINAPI control(DWORD event) {
    if(event==CTRL_C_EVENT || event==CTRL_BREAK_EVENT) {interrupted.store(true);return TRUE;}return FALSE;
}
struct Failure : std::runtime_error {
    int code;Failure(const char* message,int exit_code=4):std::runtime_error(message),code(exit_code){}
};
class Terminal final {
public:
    HANDLE input=GetStdHandle(STD_INPUT_HANDLE),output=GetStdHandle(STD_OUTPUT_HANDLE);
    HANDLE original=INVALID_HANDLE_VALUE,screen=INVALID_HANDLE_VALUE;
    DWORD original_mode=0,changed_bits=0;
    bool mode_changed=false,handler=false,active=false,linear=false;
    unsigned width=0,height=0;
    std::array<bool,256> pressed{};
    wchar_t high=0;
    std::vector<std::string> last_lines;
    std::uint64_t shell_sequence=0;
    HANDLE prompt_handle=INVALID_HANDLE_VALUE;
    COORD prompt_origin{};
    DWORD prompt_cells=0;
    bool prompt_active=false,shell_linear=false;
    ~Terminal() {close();}
    bool close() noexcept {
        bool ok=true;
        if(!clear_prompt())ok=false;
        if(active) {if(!SetConsoleActiveScreenBuffer(original))ok=false;active=false;}
        if(mode_changed) {
            DWORD current=0;
            if(!GetConsoleMode(input,&current) || !SetConsoleMode(input,(current&~changed_bits)|(original_mode&changed_bits)))ok=false;
            mode_changed=false;
        }
        if(handler) {if(!SetConsoleCtrlHandler(control,FALSE))ok=false;handler=false;}
        if(screen!=INVALID_HANDLE_VALUE) {if(!CloseHandle(screen))ok=false;screen=INVALID_HANDLE_VALUE;}
        if(original!=INVALID_HANDLE_VALUE) {if(!CloseHandle(original))ok=false;original=INVALID_HANDLE_VALUE;}
        return ok;
    }
    bool geometry(HANDLE handle) {
        CONSOLE_SCREEN_BUFFER_INFO info={};if(!GetConsoleScreenBufferInfo(handle,&info))return false;
        width=static_cast<unsigned>(info.srWindow.Right-info.srWindow.Left+1);
        height=static_cast<unsigned>(info.srWindow.Bottom-info.srWindow.Top+1);return width && height;
    }
    bool screen_capable() const {return width>=60 && height>=16;}
    bool activate() {
        if(original==INVALID_HANDLE_VALUE)original=CreateFileW(L"CONOUT$",GENERIC_READ|GENERIC_WRITE,
            FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_EXISTING,0,nullptr);
        if(original==INVALID_HANDLE_VALUE)return false;
        if(screen==INVALID_HANDLE_VALUE)screen=CreateConsoleScreenBuffer(GENERIC_READ|GENERIC_WRITE,
            FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,CONSOLE_TEXTMODE_BUFFER,nullptr);
        if(screen==INVALID_HANDLE_VALUE)return false;
        CONSOLE_CURSOR_INFO cursor={1,FALSE};
        if(!SetConsoleCursorInfo(screen,&cursor) || !SetConsoleActiveScreenBuffer(screen))return false;
        active=true;return true;
    }
    void begin(const std::string& style) {
        DWORD pending=0,out_mode=0;
        if(!GetConsoleMode(input,&original_mode) || !GetNumberOfConsoleInputEvents(input,&pending) ||
            !GetConsoleMode(output,&out_mode) || !geometry(output))throw Failure("frontend_unavailable",3);
        linear=style=="linear" || !screen_capable();
        if(style=="screen" && linear)throw Failure("terminal_size_unavailable",3);
        if(!linear && !activate()) {if(style=="screen")throw Failure("terminal_screen_unavailable",3);linear=true;}
        const DWORD desired=(original_mode|ENABLE_WINDOW_INPUT|ENABLE_EXTENDED_FLAGS)&
            ~(ENABLE_ECHO_INPUT|ENABLE_LINE_INPUT|ENABLE_QUICK_EDIT_MODE|ENABLE_MOUSE_INPUT|ENABLE_VIRTUAL_TERMINAL_INPUT);
        changed_bits=original_mode^desired;
        if(!SetConsoleMode(input,desired))throw Failure("terminal_input_unavailable",3);
        mode_changed=true;interrupted.store(false);
        if(!SetConsoleCtrlHandler(control,TRUE))throw Failure("terminal_control_unavailable");handler=true;
        // The ignore-Ctrl+C attribute can be inherited from a launcher. The
        // interactive child opts into its own cancellation handler; existing
        // processes and their handler lists are unaffected.
        if(!SetConsoleCtrlHandler(nullptr,FALSE))throw Failure("terminal_control_unavailable");
    }
    void toggle() {
        if(!clear_prompt())throw Failure("terminal_output_error");
        shell_linear=false;
        if(!linear) {
            if(active && !SetConsoleActiveScreenBuffer(original))throw Failure("terminal_restore_failed");
            active=false;linear=true;geometry(output);
        } else {
            if(geometry(output) && screen_capable() && activate())linear=false;
        }
    }
    void write_lines(const std::vector<std::string>& lines) {
        const HANDLE target=active?screen:output;
        // All model text is ASCII escaped. Explicit W output is code-page independent.
        for(const auto& line:lines) {
            std::wstring text(line.begin(),line.end());text+=L"\r\n";
            std::size_t position=0;
            while(position<text.size()) {
                DWORD written=0;const auto count=static_cast<DWORD>((std::min)(text.size()-position,std::size_t(4096)));
                if(!WriteConsoleW(target,text.data()+position,count,&written,nullptr) || !written)throw Failure("terminal_output_error");
                position+=written;
            }
        }
    }
    template<class Model>void draw_frame(Model& model) {
        const HANDLE target=active?screen:output;
        if(!geometry(target))throw Failure("terminal_geometry_unavailable");
        const unsigned columns=(std::min)(width,240u),rows=(std::min)(height,80u);
        const bool use_linear=linear || !screen_capable();
        const auto lines=model.render(columns,rows,use_linear);
        if(use_linear || lines.size()>rows) {if(lines!=last_lines)write_lines(lines);last_lines=lines;return;}
        last_lines.clear();
        CONSOLE_SCREEN_BUFFER_INFO info={};if(!GetConsoleScreenBufferInfo(target,&info))throw Failure("terminal_geometry_unavailable");
        std::vector<CHAR_INFO> frame(columns*rows);
        // The original host attributes are retained; focus also has textual markers.
        for(auto& cell:frame) {cell.Char.UnicodeChar=L' ';cell.Attributes=info.wAttributes;}
        for(std::size_t y=0;y<lines.size();++y)for(std::size_t x=0;x<lines[y].size() && x<columns;++x)
            frame[y*columns+x].Char.UnicodeChar=static_cast<unsigned char>(lines[y][x]);
        SMALL_RECT area={info.srWindow.Left,info.srWindow.Top,static_cast<SHORT>(info.srWindow.Left+columns-1),static_cast<SHORT>(info.srWindow.Top+rows-1)};
        const SMALL_RECT expected=area;
        if(!WriteConsoleOutputW(target,frame.data(),{static_cast<SHORT>(columns),static_cast<SHORT>(rows)},{0,0},&area))throw Failure("terminal_output_error");
        if(area.Left!=expected.Left || area.Top!=expected.Top || area.Right!=expected.Right || area.Bottom!=expected.Bottom)
            geometry(target); // A resize raced the write; next bounded iteration redraws.
    }
    void draw(TuiModel& model) {draw_frame(model);}
    bool clear_prompt() noexcept {
        if(!prompt_active)return true;prompt_active=false;
        CONSOLE_SCREEN_BUFFER_INFO info{};
        if(!GetConsoleScreenBufferInfo(prompt_handle,&info))return false;
        // A caller resize may shorten or remove our row. Never clear into the
        // next row merely because the former prompt occupied more columns.
        if(prompt_origin.X>=info.dwSize.X || prompt_origin.Y>=info.dwSize.Y) {prompt_cells=0;return true;}
        const auto cells=(std::min)(prompt_cells,static_cast<DWORD>(info.dwSize.X-prompt_origin.X));prompt_cells=0;
        DWORD written=0;
        return FillConsoleOutputCharacterW(prompt_handle,L' ',cells,prompt_origin,&written) && written==cells &&
            SetConsoleCursorPosition(prompt_handle,prompt_origin);
    }
    void draw(ShellModel& model) {
        const HANDLE target=active?screen:output;
        if(!geometry(target))throw Failure("terminal_geometry_unavailable");
        if(!linear && screen_capable()) {
            if(!clear_prompt())throw Failure("terminal_output_error");shell_linear=false;draw_frame(model);return;
        }
        // Stream complete records once, then edit only one explicitly owned
        // prompt row. Linear mode never republishes a whole result per keystroke.
        auto lines=model.linear_records(shell_sequence);
        if(!shell_linear) {lines.insert(lines.begin(),"DiskEd shell | IMAGE / FAKE PROTOTYPE | linear");shell_linear=true;}
        if(!lines.empty()) {if(!clear_prompt())throw Failure("terminal_output_error");write_lines(lines);}
        CONSOLE_SCREEN_BUFFER_INFO info{};
        if(!GetConsoleScreenBufferInfo(target,&info))throw Failure("terminal_geometry_unavailable");
        if(!prompt_active) {
            if(info.dwCursorPosition.X) {write_lines({""});if(!GetConsoleScreenBufferInfo(target,&info))throw Failure("terminal_geometry_unavailable");}
            prompt_origin=info.dwCursorPosition;prompt_handle=target;prompt_active=true;
        }
        const auto columns=(std::max)(1u,(std::min)({width,240u,static_cast<unsigned>(info.dwSize.X-prompt_origin.X)}));
        const auto prompt=model.prompt(columns>1?columns-1:1);
        const auto cells=static_cast<DWORD>((std::max)(static_cast<std::size_t>(prompt_cells),prompt.text.size()));
        DWORD written=0;
        if(!FillConsoleOutputCharacterW(target,L' ',(std::min)(cells,static_cast<DWORD>(columns)),prompt_origin,&written))throw Failure("terminal_output_error");
        const std::wstring text(prompt.text.begin(),prompt.text.end());
        if(!WriteConsoleOutputCharacterW(target,text.data(),static_cast<DWORD>(text.size()),prompt_origin,&written) || written!=text.size())throw Failure("terminal_output_error");
        prompt_cells=static_cast<DWORD>(text.size());
        const COORD cursor={static_cast<SHORT>(prompt_origin.X+prompt.cursor),prompt_origin.Y};
        if(!SetConsoleCursorPosition(target,cursor))throw Failure("terminal_output_error");
    }
    bool next(TuiInput& event,bool& resize) {
        resize=false;const DWORD ready=WaitForSingleObject(input,100);
        if(ready==WAIT_TIMEOUT)return false;
        if(ready!=WAIT_OBJECT_0)throw Failure("terminal_input_error");
        INPUT_RECORD record={};DWORD count=0;
        if(!ReadConsoleInputW(input,&record,1,&count) || count!=1)throw Failure("terminal_input_error");
        if(record.EventType==WINDOW_BUFFER_SIZE_EVENT) {resize=true;return false;}
        if(record.EventType!=KEY_EVENT)return false;
        const auto& key=record.Event.KeyEvent;const auto vk=key.wVirtualKeyCode;
        if(vk>=pressed.size())return false;
        if(!key.bKeyDown) {pressed[vk]=false;return false;}
        const bool repeated=pressed[vk] || key.wRepeatCount>1;pressed[vk]=true;
        event={TuiKey::Text,"",repeated};
        const bool ctrl=(key.dwControlKeyState&(LEFT_CTRL_PRESSED|RIGHT_CTRL_PRESSED))!=0;
        const bool alt=(key.dwControlKeyState&(LEFT_ALT_PRESSED|RIGHT_ALT_PRESSED))!=0;
        if(ctrl && vk=='C') {event.key=TuiKey::F10;return true;}
        if(ctrl || alt) {high=0;return false;}
        switch(vk) {
        case VK_UP:event.key=TuiKey::Up;break;case VK_DOWN:event.key=TuiKey::Down;break;
        case VK_LEFT:event.key=TuiKey::Left;break;case VK_RIGHT:event.key=TuiKey::Right;break;
        case VK_HOME:event.key=TuiKey::Home;break;case VK_END:event.key=TuiKey::End;break;case VK_DELETE:event.key=TuiKey::Delete;break;
        case VK_PRIOR:event.key=TuiKey::PageUp;break;case VK_NEXT:event.key=TuiKey::PageDown;break;
        case VK_RETURN:event.key=TuiKey::Enter;break;
        case VK_TAB:event.key=key.dwControlKeyState&SHIFT_PRESSED?TuiKey::BackTab:TuiKey::Tab;break;
        case VK_BACK:event.key=TuiKey::Backspace;break;case VK_ESCAPE:event.key=TuiKey::Escape;break;
        case VK_F2:event.key=TuiKey::F2;break;case VK_F3:event.key=TuiKey::F3;break;
        case VK_F4:event.key=TuiKey::F4;break;case VK_F5:event.key=TuiKey::F5;break;
        case VK_F6:event.key=TuiKey::F6;break;case VK_F9:event.key=TuiKey::F9;break;
        case VK_F10:event.key=TuiKey::F10;break;
        default: {
            const wchar_t ch=key.uChar.UnicodeChar;
            if(ch>=0xd800 && ch<=0xdbff) {high=ch;return false;}
            wchar_t units[2]={ch,0};int length=1;
            if(ch>=0xdc00 && ch<=0xdfff) {if(!high)return false;units[0]=high;units[1]=ch;length=2;}
            high=0;if(ch<32 || ch==127)return false;
            char bytes[8]={};const int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,units,length,bytes,8,nullptr,nullptr);
            if(!size)return false;
            const unsigned copies=(std::min)(static_cast<unsigned>(key.wRepeatCount),4097u);
            for(unsigned i=0;i<copies;++i)event.text.append(bytes,static_cast<std::size_t>(size));
            break;
        }
        }
        if(event.key!=TuiKey::Text)high=0;
        return true;
    }
};
}
int run_windows_tui(const std::string& style,const std::function<std::unique_ptr<TuiModel>()>& create) {
    try {
        Terminal terminal;terminal.begin(style);auto model=create();terminal.draw(*model);
#ifdef DISKED_TUI_TEST_FAULT
        // Dedicated test executable only; never enabled in disked.exe.
        throw std::runtime_error("injected_tui_failure");
#endif
        while(!model->done() && !interrupted.load()) {
            if(model->tick())terminal.draw(*model);
            TuiInput event{TuiKey::Text,"",false};bool resize=false;
            if(terminal.next(event,resize)) {
                model->input(event);if(model->take_toggle())terminal.toggle();
                if(!model->done())terminal.draw(*model);
            } else if(resize && !terminal.linear)terminal.draw(*model);
        }
        if(!terminal.close())throw Failure("terminal_restore_failed");return 0;
    } catch(const Failure& failure) {std::fprintf(stderr,"disked: %s\n",failure.what());return failure.code;}
}
int run_windows_shell(const std::string& style,const std::function<std::unique_ptr<ShellModel>()>& create) {
    try {
        Terminal terminal;terminal.begin(style);auto model=create();terminal.draw(*model);
#ifdef DISKED_TUI_TEST_FAULT
        throw std::runtime_error("injected_shell_failure");
#endif
        while(!model->done() && !interrupted.load()) {
            if(model->tick())terminal.draw(*model);
            TuiInput event{TuiKey::Text,"",false};bool resize=false;
            if(terminal.next(event,resize)) {
                model->input(event);if(model->take_toggle())terminal.toggle();
                if(!model->done())terminal.draw(*model);
            } else if(resize)terminal.draw(*model);
        }
        if(!terminal.close())throw Failure("terminal_restore_failed");return 0;
    } catch(const Failure& failure) {std::fprintf(stderr,"disked: %s\n",failure.what());return failure.code;}
}
}
