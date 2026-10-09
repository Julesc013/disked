#include "export_fixture.h"
#include <cstdio>
using V=disked::json::Value;namespace e=disked::evidence::proposal;using namespace export_fixture;
namespace {
V bindings() {
    return V::object().put("destination",V::object().put("identity",V::string("destination.fixture")).put("epoch",V::string(e::export_digest("parent")))
        .put("location",V::string("fixture-output")).put("access",V::string("create-write")).put("verification",V::string("readback-sha256")))
        .put("producer",V::object().put("identity",V::string("producer.fixture")).put("epoch",V::string(e::export_digest("producer")))
        .put("location",V::string("fixture-producer")).put("access",V::string("read")).put("digest",V::string(e::export_digest("fixture-code"))));
}
class Ports final:public e::ExportPorts {
public:
    V resources;std::string fault,bytes;std::uint64_t observations=0,writes=0,reads=0;bool created=false,flushed=false;
    Ports(const V& r,const std::string& f):resources(r),fault(f) {}
    V observe() override {
        ++observations;auto v=resources;if(fault=="binding-before" || (fault=="binding-after" && created))v.fields["destination"].fields["epoch"]=V::string(e::export_digest("replaced"));
        return v;
    }
    void create() override {
        if(fault=="create-refused")throw e::CreationRefusal("fixture_no_creation");if(fault=="create-unknown")throw e::Error("fixture_create_unknown");created=true;
        if(fault=="created-then-error")throw e::Error("fixture_created_error");
    }
    std::uint32_t write(std::uint64_t offset,const char* p,std::uint32_t n) override {
        ++writes;if(offset!=bytes.size())throw e::Error("fixture_offset");if(fault=="write-error")throw e::Error("fixture_write_error");
        const auto count=fault=="write-short"?n/2:n;bytes.append(p,count);if(fault=="write-ack-lost")throw e::Error("fixture_ack_lost");return fault=="write-oversized"?n+1:count;
    }
    void flush() override {if(fault=="flush-error")throw e::Error("fixture_flush_error");flushed=true;}
    std::string read(std::uint64_t offset,std::uint32_t n) override {
        ++reads;if(fault=="read-error")throw e::Error("fixture_read_error");auto s=bytes.substr(static_cast<std::size_t>(offset),n);
        if(fault=="read-short")s.pop_back();if(fault=="read-oversized")s+='x';if(fault=="read-corrupt")s[0]^=1;return s;
    }
    std::uint64_t size() override {return bytes.size()+(fault=="wrong-size"?1:0);}
    bool stop_requested() override {return fault=="cancel-before" || (fault=="cancel-created" && created) || (fault=="cancel-written" && writes) || (fault=="cancel-flushed" && flushed);}
};
}
int main() {
    try {
        std::string input;char block[4096];for(;;) {const auto n=std::fread(block,1,sizeof(block),stdin);input.append(block,n);if(input.size()>65536)return 2;if(n<sizeof(block))break;}
        const auto v=disked::json::parse(input);const auto report=make_case(flag(v,"large"),flag(v,"controls"));const auto policy=v.find("policy")?*v.find("policy"):default_policy();
        const e::SupportArtifact artifact(report,policy);const auto resources=v.find("resources")?*v.find("resources"):bindings();const e::ExportDefinition definition(artifact,resources);
        Ports ports(resources,v.find("fault")?text(*v.find("fault")):"");const auto outcome=e::execute_export(definition,grant(v,definition.digest()),ports);
        auto out=V::object().put("definition",definition.value()).put("definition_digest",V::string(definition.digest())).put("artifact_preview",preview(artifact))
            .put("outcome",outcome.view()).put("observations",V::string(std::to_string(ports.observations))).put("created",V::boolean_value(ports.created))
            .put("writes",V::string(std::to_string(ports.writes))).put("reads",V::string(std::to_string(ports.reads))).put("output_bytes",V::string(std::to_string(ports.bytes.size())))
            .put("output_digest",V::string(e::export_digest(ports.bytes))).put("physical_io",V::boolean_value(false)).put("file_io",V::boolean_value(false));
        auto limits=e::case_limits();limits.bytes=2097152;std::puts(disked::json::dump(out,limits).c_str());return 0;
    }catch(const std::exception& error) {std::puts(disked::json::dump(V::object().put("refusal",V::string(error.what()))).c_str());return 3;}
}
