#include "gpt_execution.h"
#include "fixture_repair.h"
#include "gpt_capture.h"
#include "bootstrap_registry.h"
#include <iostream>
#include <memory>

namespace e=disked::execution::proposal;namespace p=disked::planner::proposal;namespace f=disked::image::fixture;using V=disked::json::Value;
namespace {
void require(bool ok,const char* code="fixture_probe_shape") {if(!ok)throw e::FixtureError(code);}
const V& field(const V& v,const char* key) {const auto x=v.find(key);require(x!=nullptr);return *x;}
std::string text(const V& v,const char* key) {const auto& x=field(v,key);require(x.kind==V::Kind::string);return x.text;}
unsigned digit(char c) {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);throw e::FixtureError("fixture_probe_hex");}
e::Bytes unhex(const std::string& value) {require(value.size()%2==0 && value.size()<=16777216,"fixture_probe_image_budget");e::Bytes out(value.size()/2);for(std::size_t i=0;i<out.size();++i)out[i]=static_cast<unsigned char>(digit(value[i*2])*16+digit(value[i*2+1]));return out;}
std::uint64_t native(const de_u64& n) {char out[21];require(de_u64_format(&n,out,sizeof(out))==DE_OK);return std::stoull(out);}
V line() {
    std::string raw;char c;while(std::cin.get(c) && c!='\n') {require(raw.size()<17825792,"fixture_probe_input_budget");raw+=c;}require(!raw.empty(),"fixture_probe_input");
    disked::json::Limits limits;limits.bytes=17825792;limits.string_bytes=16777216;limits.values=8192;return disked::json::parse(raw,limits);
}
f::Fault fault(const V& input) {const auto x=input.find("fault");if(!x)return {};require(x->kind==V::Kind::object && x->fields.size()==2);return {text(*x,"stage"),text(*x,"action")};}
void emit(const V& value) {disked::json::Limits limits;limits.bytes=262144;limits.values=32768;std::cout<<disked::json::dump(value,limits)<<'\n'<<std::flush;}
}
int main(int argc,char** argv) {
    try {
        require(argc==1 || (argc==3 && std::string(argv[1])=="--fixture-parent"));const auto input=line();require(input.kind==V::Kind::object);
        const auto phase=text(input,"phase"),unit=text(input,"logical_block_bytes"),source=text(input,"authoritative_copy");require(phase=="create" || phase=="inspect" || phase=="restore" || phase=="restore-inspect");require(unit=="512" || unit=="4096");require(source=="primary" || source=="backup");
        for(const auto& item:input.fields)require(item.first=="phase" || item.first=="logical_block_bytes" || item.first=="authoritative_copy" || item.first=="image_hex" || item.first=="expected_capture_digest" || item.first=="expected_plan_digest" || item.first=="selection_decision_digest" || item.first=="fault" || ((phase=="inspect" || phase=="restore" || phase=="restore-inspect") && (item.first=="manifest" || item.first=="review" || item.first=="grant")) || (phase=="restore" && item.first=="attempt_id") || (phase=="restore-inspect" && (item.first=="restoration_definition" || item.first=="restoration_digest" || item.first=="restoration_review" || item.first=="restoration_grant" || item.first=="restoration_store")));
        const auto image=unhex(text(input,"image_hex"));const std::uint32_t block_bytes=unit=="4096"?4096:512;require(!image.empty() && image.size()%block_bytes==0,"fixture_probe_geometry");
        auto basis=disked::capture_gpt_regions("image:gpt-fixture",1,image.size()/block_bytes,block_bytes,[&image](const de_byte_extent& extent) {
            const auto start=native(extent.start),end=native(extent.end);if(start>=image.size())return de_view{nullptr,0};return de_view{image.data()+static_cast<std::size_t>(start),static_cast<std::size_t>(std::min<std::uint64_t>(end,image.size())-start)};
        });
        p::GptRepairSelection selection;selection.source=source=="primary"?p::GptCopy::primary:p::GptCopy::backup;
        if(const auto x=input.find("selection_decision_digest")) {require(x->kind==V::Kind::string);selection.decision_digest=x->text;}
        e::GptFixtureExecution execution(basis,text(input,"expected_capture_digest"),selection);require(execution.plan().digest()==text(input,"expected_plan_digest"),"fixture_probe_plan_binding");
        if(phase=="restore-inspect") {
            require(argc==1);const auto observation=line();require(observation.kind==V::Kind::object && observation.fields.size()==2 && text(observation,"phase")=="retained-observation");const auto observed=unhex(text(observation,"image_hex"));
            const auto history=line();require(history.kind==V::Kind::object && history.fields.size()==2 && text(history,"phase")=="retained-original-journal");const auto journal=unhex(text(history,"journal_hex"));
            auto restoration=disked::recovery::proposal::retained_gpt_restoration(execution,image,observed,journal,field(input,"manifest"),field(input,"review"),field(input,"grant"),field(input,"restoration_definition"),text(input,"restoration_digest"));
            restoration.validate_grant(field(input,"restoration_review"),field(input,"restoration_grant"));auto files=f::GptFiles::reopen_restoration_readonly(restoration.original_manifest(),field(input,"restoration_store"),fault(input));
            const auto result=restoration.inspect(*files,field(input,"restoration_review"),field(input,"restoration_grant"));emit(V::object().put("phase",V::string("restoration_inspected")).put("inspection",result).put("events",files->events()).put("fault_fired",V::boolean_value(files->fault_fired())));return 0;
        }
        if(phase=="restore") {
            require(argc==1);execution.prepare(field(input,"manifest"));auto readonly=f::GptFiles::reopen_readonly(field(input,"manifest"));
            disked::recovery::proposal::GptFixtureRestoration restoration(execution,image,*readonly,field(input,"review"),field(input,"grant"),text(input,"attempt_id"));auto prepared=restoration.prepare();prepared.put("events",readonly->events());emit(prepared);readonly.reset();
            const auto instruction=line();require(instruction.kind==V::Kind::object && instruction.fields.size()==3 && text(instruction,"phase")=="restore-execute");restoration.validate_grant(field(instruction,"review"),field(instruction,"grant"));
            auto files=f::GptFiles::reopen_for_restoration(restoration.original_manifest(),restoration.journal_name(),fault(input));
            // The new store is visible before effect dispatch for crash evidence.
            emit(V::object().put("phase",V::string("restoration_store")).put("store",files->restoration_store()));
            const auto result=restoration.execute(*files,field(instruction,"review"),field(instruction,"grant"));emit(V::object().put("phase",V::string("restoration_finished")).put("restoration",result).put("events",files->events()).put("fault_fired",V::boolean_value(files->fault_fired())));
            const auto status=text(result,"status");return status=="unresolved"?6:status=="refused"?3:0;
        }
        if(phase=="inspect") {
            require(argc==1);execution.prepare(field(input,"manifest"));auto files=f::GptFiles::reopen_readonly(field(input,"manifest"),fault(input));auto result=execution.inspect(*files,field(input,"review"),field(input,"grant"));emit(V::object().put("phase",V::string("inspected")).put("inspection",result).put("events",files->events()).put("fault_fired",V::boolean_value(files->fault_fired())));return 0;
        }
        require(argc==3);auto files=f::GptFiles::create(argv[2],image,bootstrap::source_revision,fault(input));emit(execution.prepare(files->manifest()));
        const auto instruction=line();require(instruction.kind==V::Kind::object && instruction.fields.size()>=3 && instruction.fields.size()<=5 && text(instruction,"phase")=="execute");
        for(const auto& item:instruction.fields)require(item.first=="phase" || item.first=="review" || item.first=="grant" || item.first=="cancel_at" || item.first=="repeat");
        const auto cancel=instruction.find("cancel_at");if(cancel)require(cancel->kind==V::Kind::string);
        const auto result=execution.execute(*files,field(instruction,"review"),field(instruction,"grant"),cancel?cancel->text:"none");
        auto output=V::object().put("phase",V::string("finished")).put("execution",result);
        if(const auto again=instruction.find("repeat")) {require(again->kind==V::Kind::boolean);if(again->boolean)output.put("repeat_execution",execution.execute(*files,field(instruction,"review"),field(instruction,"grant")));}
        output.put("events",files->events()).put("fault_fired",V::boolean_value(files->fault_fired()));emit(output);
        const auto status=text(result,"status");return status=="unresolved"?6:status=="refused"?3:0;
    }catch(const std::exception& error) {emit(V::object().put("phase",V::string("refused")).put("diagnostic",V::string(error.what())).put("product_writes_admitted",V::boolean_value(false)));return 3;}
}
