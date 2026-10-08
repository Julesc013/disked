#include "pipeline.h"
#include "sha256.h"
#include <algorithm>
#include <cstdio>
#include <map>

namespace {
using V=disked::json::Value;
using namespace disked::acquisition;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw Error("fixture_shape");return *p;}
std::string string(const V& v,const char* key,const char* fallback="") {const auto p=v.find(key);return p?p->text:fallback;}
std::uint64_t numeric(const V& v,const char* key,std::uint64_t fallback=0) {const auto p=v.find(key);return p?std::stoull(p->text):fallback;}
bool boolean(const V& v,const char* key) {const auto p=v.find(key);return p && p->boolean;}
std::string hex(const std::vector<unsigned char>& bytes) {
    const char alphabet[]="0123456789abcdef";std::string out;
    for(const auto c:bytes) {out+=alphabet[c>>4];out+=alphabet[c&15];}return out;
}
std::vector<unsigned char> unhex(const std::string& s) {
    if(s.size()%2 || s.size()>6*1024*1024)throw Error("fixture_bytes_limit");std::vector<unsigned char> out;
    for(std::size_t i=0;i<s.size();i+=2)out.push_back(static_cast<unsigned char>(std::stoul(s.substr(i,2),nullptr,16)));return out;
}
class Fake final:public Ports {
    std::size_t cursor_=0;
    std::map<std::string,std::uint64_t> counts_;
public:
    V active,settings=V::object(),trace=V::array();
    std::vector<unsigned char> source,destination;
    std::vector<Record> records;
    bool exists=false;
    void before(const std::string& name) {
        ++counts_[name];if(trace.items.size()<512)trace.items.push_back(V::string(name));
        if(string(settings,"crash")==name && counts_[name]==numeric(settings,"crash_occurrence",1) && !boolean(settings,"crash_after"))throw Error("fixture_interrupt");
    }
    void after(const std::string& name) {
        if(string(settings,"change_binding_after")==name && counts_[name]==numeric(settings,"change_occurrence",1)) {
            auto& b=active.fields.at(string(settings,"change_role","source"));b.put("epoch",V::string(get(b,"epoch").text+"-changed"));
        }
        if(string(settings,"crash")==name && counts_[name]==numeric(settings,"crash_occurrence",1) && boolean(settings,"crash_after"))throw Error("fixture_interrupt");
    }
    void stage(const V& v) {settings=v;counts_.clear();trace=V::array();}
    V observe() override {
        before("observe");auto value=active;
        if(const auto replacement=settings.find("observed_resources"))value=*replacement;
        after("observe");return value;
    }
    V create_outputs(const Plan& p) override {
        before("create");if(exists || boolean(settings,"preexisting"))throw CreationRefusal("fixture_destination_exists");
        exists=true;destination.assign(static_cast<std::size_t>(p.bytes),0);records.clear();
        for(const char* role:{"destination","map"}) {
            auto& b=active.fields.at(role);const std::string id=std::string("owned-")+role;
            b.put("identity",V::string(id)).put("epoch",V::string("owned-generation-1")).put("aliases",V::array());b.fields.at("aliases").items.push_back(V::string(id));
        }
        after("create");return active;
    }
    void open_resume() override {before("open_resume");if(!exists)throw Error("fixture_no_outputs");cursor_=0;after("open_resume");}
    Record next_record() override {
        before("next_record");if(cursor_==records.size())return {"",true,true};
        auto out=records[cursor_++];after("next_record");return out;
    }
    void discard_incomplete_tail() override {
        before("discard_tail");if(records.empty() || records.back().complete)throw Error("fixture_tail");records.pop_back();after("discard_tail");
    }
    void append_record(const std::string& bytes) override {
        const auto v=disked::json::parse(bytes);const auto name="append:"+get(v,"type").text;before(name);
        if(boolean(settings,"torn_append")) {
            records.push_back({bytes.substr(0,bytes.size()/2),false,false});throw Error("fixture_torn_append");
        }
        records.push_back({bytes,true,false});after(name);
    }
    void flush_map() override {before("flush_map");after("flush_map");}
    Read read_source(std::uint64_t offset,std::uint32_t size) override {
        before("read_source");Read r;
        if(offset>source.size())r.error="fixture_range";
        else {
            const auto end=std::min<std::uint64_t>(source.size(),offset+size);
            r.bytes.assign(source.begin()+static_cast<std::size_t>(offset),source.begin()+static_cast<std::size_t>(end));
            const auto failed=settings.find("read_error_offset");
            if(failed && offset==std::stoull(failed->text) && counts_["read_source"]<=numeric(settings,"error_calls",1000000))r.error="fixture_unreadable";
            if(boolean(settings,"short_read") && !r.bytes.empty())r.bytes.pop_back();
            if(boolean(settings,"oversized_read"))r.bytes.push_back(7);
        }
        after("read_source");return r;
    }
    void write_destination(std::uint64_t offset,const std::vector<unsigned char>& bytes) override {
        before("write_destination");if(offset>destination.size() || bytes.size()>destination.size()-offset)throw Error("fixture_range");
        auto count=bytes.size();if(settings.find("partial_write"))count=std::min<std::size_t>(count,static_cast<std::size_t>(numeric(settings,"partial_write")));
        std::copy(bytes.begin(),bytes.begin()+count,destination.begin()+static_cast<std::size_t>(offset));
        if(boolean(settings,"corrupt_write") && count)destination[static_cast<std::size_t>(offset)]^=1;
        if(settings.find("partial_write"))throw Error("fixture_partial_write");after("write_destination");
    }
    void flush_destination() override {before("flush_destination");after("flush_destination");}
    Read read_destination(std::uint64_t offset,std::uint32_t size) override {
        before("read_destination");Read r;
        if(offset>destination.size())r.error="fixture_range";
        else {const auto end=std::min<std::uint64_t>(destination.size(),offset+size);r.bytes.assign(destination.begin()+static_cast<std::size_t>(offset),destination.begin()+static_cast<std::size_t>(end));}
        after("read_destination");return r;
    }
    bool stop_requested() override {
        before("stop");if(!settings.find("stop_after_bytes"))return false;
        std::uint64_t bytes=0;for(const auto& r:records)if(r.complete) {
            const auto v=disked::json::parse(r.bytes);if(get(v,"type").text=="checkpoint") {const auto& c=get(v,"payload");bytes=std::stoull(get(c,"offset").text)+std::stoull(get(c,"length").text);}
        }
        return bytes>=numeric(settings,"stop_after_bytes");
    }
};
}
int main() {
    try {
        std::string input;char buffer[8192];for(;;) {const auto got=std::fread(buffer,1,sizeof(buffer),stdin);input.append(buffer,got);if(input.size()>8*1024*1024)return 2;if(got<sizeof(buffer))break;}
        disked::json::Limits l;l.bytes=8*1024*1024;l.string_bytes=6*1024*1024;l.values=4096;
        const auto fixture=disked::json::parse(input,l);const auto plan=prepare(get(fixture,"plan"));
        if(plan.bytes>3*1024*1024)throw Error("fixture_size");
        Fake io;io.active=get(plan.definition,"resources");io.source=unhex(string(fixture,"source_hex"));
        if(const auto a=fixture.find("active"))io.active=*a;
        if(fixture.find("destination_hex")) {io.destination=unhex(string(fixture,"destination_hex"));io.exists=true;}
        if(const auto rows=fixture.find("records"))for(const auto& r:rows->items)io.records.push_back({get(r,"bytes").text,get(r,"complete").boolean,false});
        Grant grant{plan.digest,true,true,true,true};V results=V::array();
        for(const auto& step:get(fixture,"steps").items) {
            io.stage(step);Grant current=grant;
            if(step.find("grant_digest"))current.plan_digest=string(step,"grant_digest");
            if(boolean(step,"deny_source"))current.source_read=false;
            if(boolean(step,"deny_destination"))current.destination_write=false;
            if(boolean(step,"deny_map"))current.map_write=false;
            if(boolean(step,"deny_host"))current.host_effects=false;
            if(const auto delta=step.find("source_xor")) {const auto pos=std::stoull(delta->text);if(pos>=io.source.size())throw Error("fixture_range");io.source[static_cast<std::size_t>(pos)]^=1;}
            if(const auto delta=step.find("destination_xor")) {const auto pos=std::stoull(delta->text);if(pos>=io.destination.size())throw Error("fixture_range");io.destination[static_cast<std::size_t>(pos)]^=1;}
            const auto result=execute(plan,current,io,boolean(step,"resume"));results.items.push_back(V::object().put("outcome",result.report()).put("trace",io.trace));
        }
        auto rows=V::array();for(const auto& r:io.records)rows.items.push_back(V::object().put("bytes",V::string(r.bytes)).put("complete",V::boolean_value(r.complete)));
        const auto output=V::object().put("plan_digest",V::string(plan.digest)).put("results",results).put("active",io.active)
            .put("records",rows).put("destination_hex",V::string(hex(io.destination))).put("source_hex",V::string(hex(io.source)));
        l.bytes=16*1024*1024;const auto encoded=disked::json::dump(output,l);std::puts(encoded.c_str());return 0;
    } catch(const std::exception& e) {
        const auto output=V::object().put("refusal",V::string(e.what()));std::puts(disked::json::dump(output).c_str());return 3;
    }
}
