#include "watch.h"
#include <iostream>
using namespace disked;using json::Value;
std::string field(const Value& value,const char* name,const std::string& fallback="") {const auto* item=value.find(name);return item?item->text:fallback;}
int main() {
    std::string line;
    while(std::getline(std::cin,line))try {
        const auto value=json::parse(line);Value out;
        if(field(value,"op")=="validate")out=Value::object().put("error",Value::string(validate_fake_event(*value.find("event"))));
        else if(field(value,"op")=="queue") {
            WatchQueue queue;for(unsigned i=0;i<64;++i)queue.push(*value.find("event"));
            std::string error;try {queue.push(*value.find("event"));}catch(const std::invalid_argument& e) {error=e.what();}
            unsigned count=0;Value item;while(queue.pop(item))++count;
            queue.close();out=Value::object().put("error",Value::string(error)).put("count",Value::number(std::to_string(count)))
                .put("after_close",Value::boolean_value(queue.push(*value.find("event"))));
        } else {
            WatchReader reader(field(value,"operation_id"),field(value,"worker_epoch"),field(value,"sequence","0"),field(value,"digest",std::string(64,'0')),
                value.find("snapshot") && value.find("snapshot")->boolean);
            auto results=Value::array();
            for(const auto& event:value.find("events")->items) {
                auto row=Value::object();
                try {row.put("accepted",Value::boolean_value(reader.accept(event))).put("error",Value::string("")).put("preserved",event);}
                catch(const std::exception& e) {row.put("error",Value::string(e.what()));}
                row.put("sequence",Value::string(reader.sequence())).put("digest",Value::string(reader.digest()));results.items.push_back(row);
            }
            out=Value::object().put("results",results);
        }
        json::Limits limit;limit.bytes=1048576;std::cout<<json::dump(out,limit)<<std::endl;
    } catch(const std::exception& e) {std::cout<<json::dump(Value::object().put("error",Value::string(e.what())))<<std::endl;}
}
