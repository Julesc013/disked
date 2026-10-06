#include "json.h"
#include <cmath>
#include <cstdlib>
#include <utility>

namespace disked { namespace json {
Error::Error(const std::string& name, std::size_t position)
    : std::runtime_error(name), code(name), offset(position) {}
Value Value::string(const std::string& value) { Value v; v.kind=Kind::string; v.text=value; return v; }
Value Value::number(const std::string& lexeme) { Value v; v.kind=Kind::number; v.text=lexeme; return v; }
Value Value::boolean_value(bool value) { Value v; v.kind=Kind::boolean; v.boolean=value; return v; }
Value Value::array() { Value v; v.kind=Kind::array; return v; }
Value Value::object() { Value v; v.kind=Kind::object; return v; }
const Value* Value::find(const std::string& key) const {
    if (kind!=Kind::object) return nullptr;
    const auto it=fields.find(key); return it==fields.end() ? nullptr : &it->second;
}
Value& Value::put(const std::string& key, Value value) {
    if (kind!=Kind::object) throw Error("internal_type_error",0);
    fields[key]=std::move(value); return *this;
}
bool valid_utf8(const std::string& text) {
    for (std::size_t i=0;i<text.size();) {
        const unsigned c=static_cast<unsigned char>(text[i++]);
        if (c<0x80) continue;
        unsigned count=0, code=0, minimum=0;
        if (c>=0xC2 && c<=0xDF) {count=1;code=c&31;minimum=0x80;}
        else if (c>=0xE0 && c<=0xEF) {count=2;code=c&15;minimum=0x800;}
        else if (c>=0xF0 && c<=0xF4) {count=3;code=c&7;minimum=0x10000;}
        else return false;
        if (count>text.size()-i) return false;
        while (count--) {
            const unsigned next=static_cast<unsigned char>(text[i++]);
            if ((next&0xC0)!=0x80) return false;
            code=(code<<6)|(next&63);
        }
        if (code<minimum || code>0x10FFFF || (code>=0xD800 && code<=0xDFFF)) return false;
    }
    return true;
}
bool decimal_u64(const std::string& text) {
    if (text.empty() || text.size()>20 || (text.size()>1 && text[0]=='0')) return false;
    for (char c:text) if (c<'0' || c>'9') return false;
    return text.size()<20 || text<="18446744073709551615";
}
namespace {
bool digit(char c) { return c>='0' && c<='9'; }
bool space(char c) { return c==' ' || c=='\t' || c=='\r' || c=='\n'; }
void append_codepoint(std::string& out, unsigned code) {
    if (code<0x80) out.push_back(static_cast<char>(code));
    else if (code<0x800) {out.push_back(static_cast<char>(0xC0|(code>>6)));out.push_back(static_cast<char>(0x80|(code&63)));}
    else if (code<0x10000) {out.push_back(static_cast<char>(0xE0|(code>>12)));out.push_back(static_cast<char>(0x80|((code>>6)&63)));out.push_back(static_cast<char>(0x80|(code&63)));}
    else {out.push_back(static_cast<char>(0xF0|(code>>18)));out.push_back(static_cast<char>(0x80|((code>>12)&63)));out.push_back(static_cast<char>(0x80|((code>>6)&63)));out.push_back(static_cast<char>(0x80|(code&63)));}
}
class Reader {
    const std::string& input;
    Limits limits;
    std::size_t offset=0, count=0;
    char peek() const { return offset<input.size() ? input[offset] : '\0'; }
    void whitespace() { while(offset<input.size() && space(input[offset])) ++offset; }
    [[noreturn]] void error(const char* code) const { throw Error(code,offset); }
    unsigned hex4() {
        unsigned value=0;
        for (int i=0;i<4;++i) {
            if (offset==input.size()) error("invalid_json");
            const char c=input[offset++]; unsigned n=16;
            if (c>='0' && c<='9') n=static_cast<unsigned>(c-'0');
            else if (c>='a' && c<='f') n=static_cast<unsigned>(c-'a'+10);
            else if (c>='A' && c<='F') n=static_cast<unsigned>(c-'A'+10);
            if (n==16) error("invalid_json");
            value=(value<<4)|n;
        }
        return value;
    }
    std::string string() {
        if (peek()!='"') error("invalid_json");
        ++offset;std::string out;
        while (offset<input.size()) {
            const unsigned char c=static_cast<unsigned char>(input[offset++]);
            if (c=='"') return out;
            if (c<32) error("invalid_json");
            if (c!='\\') out.push_back(static_cast<char>(c));
            else {
                if (offset==input.size()) error("invalid_json");
                const char escape=input[offset++];
                switch(escape) {
                case '"':out.push_back('"');break;
                case '\\':out.push_back('\\');break;
                case '/':out.push_back('/');break;
                case 'b':out.push_back('\b');break;
                case 'f':out.push_back('\f');break;
                case 'n':out.push_back('\n');break;
                case 'r':out.push_back('\r');break;
                case 't':out.push_back('\t');break;
                case 'u': {
                    unsigned code=hex4();
                    if (code>=0xD800 && code<=0xDBFF) {
                        if (input.size()-offset<2 || input[offset]!='\\' || input[offset+1]!='u') error("invalid_unicode");
                        offset+=2;const unsigned low=hex4();
                        if (low<0xDC00 || low>0xDFFF) error("invalid_unicode");
                        code=0x10000+((code-0xD800)<<10)+(low-0xDC00);
                    } else if (code>=0xDC00 && code<=0xDFFF) error("invalid_unicode");
                    append_codepoint(out,code);break;
                }
                default:error("invalid_json");
                }
            }
            if (out.size()>limits.string_bytes) error("string_limit_exceeded");
        }
        error("invalid_json");
    }
    Value number() {
        const auto start=offset;
        if (peek()=='-') ++offset;
        if (peek()=='0') ++offset;
        else {if (!digit(peek())) error("invalid_json");while (digit(peek())) ++offset;}
        if (peek()=='.') {++offset;if(!digit(peek()))error("invalid_json");while(digit(peek()))++offset;}
        if (peek()=='e' || peek()=='E') {++offset;if(peek()=='+'||peek()=='-')++offset;if(!digit(peek()))error("invalid_json");while(digit(peek()))++offset;}
        const std::string text=input.substr(start,offset-start);
        char* end=nullptr;const double converted=std::strtod(text.c_str(),&end);
        if (!std::isfinite(converted) || end!=text.c_str()+text.size()) error("nonfinite_number");
        return Value::number(text);
    }
    Value value(std::size_t depth) {
        whitespace();if(++count>limits.values)error("value_limit_exceeded");
        const char c=peek();
        if (c=='"') return Value::string(string());
        if (c=='-' || digit(c)) return number();
        if (c=='[' || c=='{') {
            if (depth>=limits.depth)error("depth_limit_exceeded");
            const bool object=c=='{';const char close=object?'}':']';++offset;
            Value out=object?Value::object():Value::array();whitespace();
            if (peek()==close) {++offset;return out;}
            for (;;) {
                if (object) {
                    whitespace();std::string key=string();whitespace();
                    if (out.fields.count(key))error("duplicate_key");
                    if(peek()!=':')error("invalid_json");++offset;
                    out.fields.emplace(std::move(key),value(depth+1));
                } else out.items.push_back(value(depth+1));
                whitespace();if(peek()==close) {++offset;return out;}
                if(peek()!=',')error("invalid_json");++offset;
            }
        }
        if(input.compare(offset,4,"null")==0) {offset+=4;return Value{};}
        if(input.compare(offset,4,"true")==0) {offset+=4;return Value::boolean_value(true);}
        if(input.compare(offset,5,"false")==0) {offset+=5;return Value::boolean_value(false);}
        error("invalid_json");
    }
public:
    Reader(const std::string& text,Limits bounds):input(text),limits(bounds) {}
    Value read() {
        if(input.size()>limits.bytes)error("frame_limit_exceeded");
        if(!valid_utf8(input))error("invalid_utf8");
        Value out=value(0);whitespace();if(offset!=input.size())error("invalid_json");return out;
    }
};
class Writer {
    Limits limits;std::string output;std::size_t count=0;
    void add(const std::string& text) {
        if(text.size()>limits.bytes-output.size())throw Error("output_limit_exceeded",output.size());
        output+=text;
    }
    void string(const std::string& text) {
        if(text.size()>limits.string_bytes || !valid_utf8(text))throw Error("invalid_output_string",0);
        add("\"");const char hex[]="0123456789abcdef";
        for(unsigned char c:text) {
            if(c=='"')add("\\\"");
            else if(c=='\\')add("\\\\");
            else if(c<32) {std::string escape="\\u00";escape+=hex[c>>4];escape+=hex[c&15];add(escape);}
            else add(std::string(1,static_cast<char>(c)));
        }
        add("\"");
    }
    void value(const Value& v,std::size_t depth) {
        if(++count>limits.values)throw Error("value_limit_exceeded",0);
        switch(v.kind) {
        case Value::Kind::null:add("null");break;
        case Value::Kind::boolean:add(v.boolean?"true":"false");break;
        case Value::Kind::string:string(v.text);break;
        case Value::Kind::number: {
            const auto checked=Reader(v.text,limits).read();
            if(checked.kind!=Value::Kind::number)throw Error("invalid_output_number",0);
            add(v.text);break;
        }
        case Value::Kind::array:
        case Value::Kind::object: {
            if(depth>=limits.depth)throw Error("depth_limit_exceeded",0);
            const bool object=v.kind==Value::Kind::object;add(object?"{":"[");bool first=true;
            if(object)for(const auto& pair:v.fields) {if(!first)add(",");first=false;string(pair.first);add(":");value(pair.second,depth+1);}
            else for(const auto& item:v.items) {if(!first)add(",");first=false;value(item,depth+1);}
            add(object?"}":"]");break;
        }
        }
    }
public:
    explicit Writer(Limits bounds):limits(bounds){}
    std::string write(const Value& v) {value(v,0);return output;}
};
}
Value parse(const std::string& input,Limits limits) {return Reader(input,limits).read();}
std::string dump(const Value& value,Limits limits) {return Writer(limits).write(value);}
}}
