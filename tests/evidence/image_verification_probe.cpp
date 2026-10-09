#include "file_verification.h"
#include "file_case.h"
#include "local_file.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
namespace e=disked::evidence::proposal;using V=disked::json::Value;
const V& get(const V& v,const char* key) {const auto p=v.find(key);if(!p)throw std::runtime_error("verification_probe_shape");return *p;}
std::string text(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::string)throw std::runtime_error("verification_probe_shape");return p.text;}
bool flag(const V& v,const char* key) {const auto& p=get(v,key);if(p.kind!=V::Kind::boolean)throw std::runtime_error("verification_probe_flag");return p.boolean;}
e::VerificationGrant grant(const V& input,const e::VerificationDefinition& definition) {
    if(const auto g=input.find("grant"))return {text(*g,"definition_digest"),flag(*g,"image_read"),flag(*g,"map_read")};
    return {definition.digest,true,true};
}
class FakePorts final:public e::VerificationPorts {
public:
    V resources;std::string rows,fault;std::vector<unsigned char> image;std::size_t cursor=0,observes=0,records=0,reads=0,stops=0;
    explicit FakePorts(const V& v):resources(get(v,"resources")),rows(text(v,"records")) {
        if(v.find("fault"))fault=text(v,"fault");const auto hex=text(v,"image_hex");if(hex.size()%2 || hex.size()>8388608)throw std::runtime_error("verification_probe_hex");
        for(std::size_t i=0;i<hex.size();i+=2) {auto nibble=[](char c)->unsigned {if(c>='0' && c<='9')return c-'0';if(c>='a' && c<='f')return c-'a'+10;throw std::runtime_error("verification_probe_hex");};image.push_back(static_cast<unsigned char>((nibble(hex[i])<<4)|nibble(hex[i+1])));}
    }
    V observe() override {++observes;auto value=resources;if((fault=="changed" && observes>=4) || (fault=="changed_once" && observes==4))value.fields["image"].put("epoch",V::string("changed"));return value;}
    disked::acquisition::Record next_record() override {
        ++records;if(cursor==rows.size())return {{},true,true};const auto newline=rows.find('\n',cursor);const auto start=cursor;
        if(newline==rows.npos) {cursor=rows.size();return {rows.substr(start),false,false};}
        cursor=newline+1;return {rows.substr(start,newline-start),true,false};
    }
    disked::acquisition::Read read_image(std::uint64_t offset,std::uint32_t n) override {
        ++reads;disked::acquisition::Read r;if(fault=="throw")throw std::runtime_error("injected read error");
        if(fault=="error") {r.error="injected-read-error";return r;}
        if(offset<=image.size()) {const auto end=offset+std::min<std::uint64_t>(n,image.size()-offset);r.bytes.assign(image.begin()+static_cast<std::size_t>(offset),image.begin()+static_cast<std::size_t>(end));}
        if(fault=="short" && !r.bytes.empty())r.bytes.pop_back();if(fault=="overread")r.bytes.resize(static_cast<std::size_t>(n)+1);return r;
    }
    bool stop_requested() override {++stops;return fault=="cancel" || (fault=="cancel_after_read" && reads>0);}
    V calls() const {return V::object().put("observe",V::string(std::to_string(observes))).put("records",V::string(std::to_string(records))).put("reads",V::string(std::to_string(reads))).put("stop",V::string(std::to_string(stops)));}
};
int main(int argc,char** argv) {
    try {
        const bool hold=argc==2 && std::strcmp(argv[1],"--hold")==0;if(argc!=1 && !hold)return 2;
        std::string bytes;for(int c=std::getchar();c!=EOF && (!hold || c!='\n');c=std::getchar()) {bytes+=static_cast<char>(c);if(bytes.size()>16777216)return 2;}
        disked::json::Limits limits;limits.bytes=16777216;limits.string_bytes=8388608;limits.values=131072;const auto input=disked::json::parse(bytes,limits);V out;
        if(input.find("plan")) {
            FakePorts ports(input);auto definition=e::prepare_verification(disked::acquisition::prepare(get(input,"plan")),ports.resources);
            const auto authority=grant(input,definition);if(input.find("tamper"))definition.digest="sha256:"+std::string(64,'0');
            const auto result=e::verify_image(definition,authority,ports);out=V::object().put("definition",definition.value).put("definition_digest",V::string(definition.digest)).put("outcome",result.view()).put("calls",ports.calls());
        }else {
            disked::FileAcquisitionCase source(text(input,"operation_id"),text(input,"state_directory"));
            const auto view=source.report().view();const auto revision=source.report().revision();const auto case_before=source.binding();
            const auto original=disked::acquisition::prepare(get(get(get(view,"before"),"definition"),"plan"));
            disked::FileImageVerification verification(original,text(input,"image"),text(input,"map"));const auto before=verification.binding();
            if(hold) {std::puts(disked::json::dump(V::object().put("event",V::string("verification-held")).put("pid",V::string(std::to_string(GetCurrentProcessId())))).c_str());std::fflush(stdout);if(std::getchar()!='x')throw std::runtime_error("verification_probe_release");}
            const auto result=verification.execute(grant(input,verification.definition()));
            out=V::object().put("definition",verification.definition().value).put("definition_digest",V::string(verification.definition().digest))
                .put("case_revision",V::string(revision)).put("case_binding_before",case_before).put("outcome",result.view()).put("before_binding",before);
            try {out.put("after_binding",verification.binding()).put("after_binding_status",V::string("available"));}
            catch(const std::exception&) {out.put("after_binding",V{}).put("after_binding_status",V::string("unavailable"));}
            try {source.check();out.put("case_revalidation",V::string("passed")).put("case_binding_after",source.binding());}
            catch(const std::exception&) {out.put("case_revalidation",V::string("unavailable")).put("case_binding_after",V{});}
        }
        std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const disked::FileVerificationError& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform_code)))).c_str());return 3;}
    catch(const disked::local_file::Error& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what())).put("platform_code",V::string(std::to_string(error.platform_code)))).c_str());return 3;}
    catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
