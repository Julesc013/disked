#include "shell_lexer.h"
#include "json.h"
namespace disked {
std::vector<std::string> ShellLine::arguments() const {
    std::vector<std::string> out;for(const auto& token:tokens)out.push_back(token.value);return out;
}
ShellLine tokenize_shell(const std::string& line,bool completion) {
    ShellLine out;
    auto error=[&](const char* code,std::size_t byte) {out.error=code;out.error_byte=byte;return out;};
    if(line.size()>shell_line_bytes)return error("shell_line_limit",shell_line_bytes);
    if(!json::valid_utf8(line))return error("invalid_argument_encoding",0);
    std::string value;char quote=0;std::size_t start=0,quote_start=0;bool active=false;
    auto finish=[&](std::size_t end) {
        if(active)out.tokens.push_back({value,start,end});value.clear();active=false;
    };
    for(std::size_t i=0;i<line.size();++i) {
        const auto c=static_cast<unsigned char>(line[i]);
        if(c<32 || c==127)return error("shell_control_input",i);
        if(quote) {
            if(c==static_cast<unsigned char>(quote)) {
                if(i+1<line.size() && line[i+1]==quote) {value.push_back(quote);++i;}
                else quote=0;
            } else value.push_back(static_cast<char>(c));
        } else if(c==' ')finish(i);
        else {
            if(!active) {start=i;active=true;if(out.tokens.size()==128)return error("shell_token_limit",i);}
            if(c=='\'' || c=='"') {quote=static_cast<char>(c);quote_start=i;}
            else if(c=='|' || c=='&' || c==';' || c=='<' || c=='>')return error("shell_operator_unsupported",i);
            else value.push_back(static_cast<char>(c));
        }
    }
    finish(line.size());out.open_quote=quote!=0;
    if(quote && !completion)return error("shell_unclosed_quote",quote_start);
    return out;
}
std::string quote_shell(const std::string& token) {
    if(!token.empty() && token.find_first_of(" '\"|&;<>")==std::string::npos)return token;
    std::string out="\"";
    for(const auto c:token) {out.push_back(c);if(c=='"')out.push_back('"');}return out+'"';
}
}
