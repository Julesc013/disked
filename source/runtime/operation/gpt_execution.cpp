#include "gpt_execution.h"
#include <algorithm>
#include <cstring>
#include <limits>

namespace disked { namespace execution { namespace proposal {
namespace {
namespace j=journal::proposal;namespace p=planner::proposal;using V=json::Value;
[[noreturn]] void fail(const char* code) {throw FixtureError(code);}
void require(bool ok,const char* code) {if(!ok)fail(code);}
std::string text(const V& v,const char* key) {const auto x=v.find(key);require(x && x->kind==V::Kind::string,"fixture_shape");return x->text;}
bool flag(const V& v,const char* key) {const auto x=v.find(key);require(x && x->kind==V::Kind::boolean,"fixture_shape");return x->boolean;}
V exact(std::uint64_t n) {return V::string(std::to_string(n));}
Bytes bytes(const std::string& s) {return Bytes(s.begin(),s.end());}
std::string hex(const unsigned char* data,std::size_t size) {const char d[]="0123456789abcdef";std::string s;for(std::size_t i=0;i<size;++i){s+=d[data[i]>>4];s+=d[data[i]&15];}return s;}
std::string hash(const Bytes& b) {const auto h=j::hash(b);return "sha256:"+hex(h.data(),h.size());}
std::string hash(const V& v) {return hash(bytes(json::dump(v)));}
unsigned digit(char c) {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);fail("fixture_digest");}
j::Digest digest(const std::string& s) {
    require(s.size()==71 && s.compare(0,7,"sha256:")==0,"fixture_digest");j::Digest out{};
    for(std::size_t i=0;i<out.size();++i)out[i]=static_cast<unsigned char>(digit(s[7+i*2])*16+digit(s[8+i*2]));
    require(std::any_of(out.begin(),out.end(),[](unsigned char b){return b!=0;}),"fixture_digest");return out;
}
j::Identity identity(const std::string& s) {require(s.size()==32,"fixture_identity");j::Identity out{};for(std::size_t i=0;i<16;++i)out[i]=static_cast<unsigned char>(digit(s[i*2])*16+digit(s[i*2+1]));require(std::any_of(out.begin(),out.end(),[](unsigned char b){return b!=0;}),"fixture_identity");return out;}
std::uint64_t integer(const std::string& s) {require(json::decimal_u64(s),"fixture_integer");return std::stoull(s);}
void closed(const V& v,std::initializer_list<const char*> keys) {
    require(v.kind==V::Kind::object && v.fields.size()==keys.size(),"fixture_shape");for(const auto key:keys)require(v.find(key)!=nullptr,"fixture_shape");
}
void manifest_shape(const V& m,std::uint64_t size) {
    closed(m,{"schema","scope","directory","root_identity","image_identity","backup_identity","journal_identity","image_bytes","provider_id","executor_digest","publisher_identity","publisher_epoch","image_before_sha256","source_revision","storage_independent"});
    require(text(m,"schema")=="org.disked.gpt-fixture-files/1" && text(m,"scope")=="owned-file-fixture" && text(m,"provider_id")=="provider.image.gpt-owned-fixture/1","fixture_scope");
    require(integer(text(m,"image_bytes"))==size && size<=8388608 && !flag(m,"storage_independent"),"fixture_scope");
    for(const auto key:{"root_identity","image_identity","backup_identity","journal_identity","executor_digest","image_before_sha256"})digest(text(m,key));
    require(text(m,"image_identity")!=text(m,"backup_identity") && text(m,"image_identity")!=text(m,"journal_identity") && text(m,"backup_identity")!=text(m,"journal_identity"),"fixture_alias");
    require(integer(text(m,"publisher_epoch"))>0,"fixture_identity");identity(text(m,"publisher_identity"));
    const auto revision=text(m,"source_revision");require(revision.size()==40 && revision.find_first_not_of("0123456789abcdef")==revision.npos,"fixture_code_identity");
    require(!text(m,"directory").empty() && text(m,"directory").size()<=960,"fixture_scope");
}
std::uint64_t multiply(std::uint64_t a,std::uint64_t b) {require(!b || a<=(std::numeric_limits<std::uint64_t>::max)()/b,"fixture_extent");return a*b;}
std::uint64_t array_offset(const Bytes& b,std::uint32_t unit) {require(b.size()>=80,"fixture_extent");std::uint64_t n=0;for(unsigned i=0;i<8;++i)n|=std::uint64_t(b[72+i])<<(8*i);return multiply(n,unit);}
struct Region {std::string name;std::uint64_t offset;Bytes value;};
std::vector<Region> regions(const p::GptRepairCapture& c) {
    return {{"protective_mbr",0,c.protective_mbr},{"primary_header",c.block_bytes,c.primary_header},{"primary_array",array_offset(c.primary_header,c.block_bytes),c.primary_array},{"backup_header",multiply(c.blocks-1,c.block_bytes),c.backup_header},{"backup_array",array_offset(c.backup_header,c.block_bytes),c.backup_array}};
}
Bytes backup(const p::GptRepairCapture& c,const p::GptRepairPlan& plan) {
    auto rows=V::array();Bytes payload;for(const auto& r:regions(c)) {
        rows.items.push_back(V::object().put("name",V::string(r.name)).put("image_offset",exact(r.offset)).put("payload_offset",exact(payload.size())).put("bytes",exact(r.value.size())).put("sha256",V::string(hash(r.value))));
        payload.insert(payload.end(),r.value.begin(),r.value.end());
    }
    const auto manifest=json::dump(V::object().put("schema",V::string("org.disked.gpt-fixture-backup/1")).put("plan_digest",V::string(plan.digest())).put("capture_digest",*plan.definition().find("capture_digest")).put("regions",rows));
    require(manifest.size()<=4096,"fixture_backup_budget");Bytes out=bytes("DEGBK001");const auto size=static_cast<std::uint32_t>(manifest.size());for(unsigned i=0;i<4;++i)out.push_back(static_cast<unsigned char>(size>>(i*8)));
    out.insert(out.end(),manifest.begin(),manifest.end());out.insert(out.end(),payload.begin(),payload.end());require(out.size()<=2117632,"fixture_backup_budget");return out;
}
p::GptRepairCapture overlay(p::GptRepairCapture c,const p::GptRepairPlan& plan,std::size_t count) {
    require(count<=plan.patches().size(),"fixture_prefix");const bool primary=text(plan.definition(),"target_copy")=="primary";
    for(std::size_t i=0;i<count;++i) {const auto& patch=plan.patches()[i];auto& raw=patch.id=="target-array"?(primary?c.primary_array:c.backup_array):(primary?c.primary_header:c.backup_header);require(patch.after.size()<=raw.size(),"fixture_extent");std::copy(patch.after.begin(),patch.after.end(),raw.begin());}return c;
}
p::GptRepairCapture recapture(GptFixturePort& port,const p::GptRepairCapture& reference) {
    port.check_ownership();auto c=reference;auto fields=std::vector<Bytes*>{&c.protective_mbr,&c.primary_header,&c.primary_array,&c.backup_header,&c.backup_array};const auto rows=regions(reference);
    for(std::size_t i=0;i<rows.size();++i) {*fields[i]=port.read_image(rows[i].offset,rows[i].value.size());require(fields[i]->size()==rows[i].value.size(),"fixture_capture_short");}port.check_ownership();return c;
}
V patch_ids(const p::GptRepairPlan& plan) {auto ids=V::array();for(const auto& patch:plan.patches())ids.items.push_back(V::string(patch.id));return ids;}
void validate_receipts(const V& m,const p::GptRepairPlan& plan,const V& review,const V& grant) {
    closed(review,{"schema","plan_digest","capture_digest","manifest_digest","reviewed","issuer","evidence_digest"});
    require(text(review,"schema")=="org.disked.gpt-fixture-review/1" && text(review,"issuer")=="fixture-controller" && flag(review,"reviewed"),"fixture_review");digest(text(review,"evidence_digest"));
    require(text(review,"plan_digest")==plan.digest() && text(review,"capture_digest")==text(plan.definition(),"capture_digest") && text(review,"manifest_digest")==hash(m),"fixture_review_binding");
    closed(grant,{"schema","plan_digest","review_digest","manifest_digest","provider_id","executor_digest","image_identity","backup_identity","journal_identity","patch_ids","allow_fixture_writes","acknowledge_proposed_journal"});
    require(text(grant,"schema")=="org.disked.gpt-fixture-grant/1" && flag(grant,"allow_fixture_writes") && flag(grant,"acknowledge_proposed_journal"),"fixture_grant");
    require(text(grant,"plan_digest")==plan.digest() && text(grant,"review_digest")==hash(review) && text(grant,"manifest_digest")==hash(m),"fixture_grant_binding");
    for(const auto key:{"provider_id","executor_digest","image_identity","backup_identity","journal_identity"})require(text(grant,key)==text(m,key),"fixture_grant_binding");
    require(json::dump(*grant.find("patch_ids"))==json::dump(patch_ids(plan)),"fixture_grant_scope");
}
j::Bindings bindings(const V& m,const p::GptRepairPlan& plan) {
    j::Bindings b;const auto id=digest(text(m,"journal_identity"));std::copy_n(id.begin(),16,b.journal.begin());b.plan=digest(plan.digest());
    b.targets=digest(hash(V::object().put("root",*m.find("root_identity")).put("image",*m.find("image_identity")).put("backup",*m.find("backup_identity")).put("journal",*m.find("journal_identity")).put("image_bytes",*m.find("image_bytes"))));
    b.providers=digest(hash(V::object().put("provider",*m.find("provider_id")).put("executor",*m.find("executor_digest"))));return b;
}
V event(const p::GptRepairPlan& plan,const Bytes& original,const std::string& kind,std::size_t index,const std::string& capture) {
    auto value=V::object().put("schema",V::string("org.disked.gpt-fixture-journal/1")).put("event",V::string(kind)).put("plan_digest",V::string(plan.digest())).put("backup_digest",V::string(hash(original))).put("prefix",exact(index)).put("capture_digest",V::string(capture));
    if(kind=="intention" || kind=="completion")value.put("patch",plan.definition().find("patches")->items[index-(kind=="completion"?1:0)]);
    return value;
}
V admission(const V& m,const p::GptRepairPlan& plan,const Bytes& original,const V& review,const V& grant) {
    return V::object().put("schema",V::string("org.disked.gpt-fixture-admission/1")).put("plan_digest",V::string(plan.digest())).put("capture_digest",*plan.definition().find("capture_digest")).put("review_digest",V::string(hash(review))).put("grant_digest",V::string(hash(grant))).put("manifest_digest",V::string(hash(m))).put("backup_digest",V::string(hash(original))).put("fixture_only",V::boolean_value(true));
}
class Buffer:public j::Source {
    const Bytes& bytes_;
public:
    explicit Buffer(const Bytes& bytes):bytes_(bytes) {}
    std::uint64_t size() override {return bytes_.size();}
    Bytes read_at(std::uint64_t start,std::size_t count) override {require(start<=bytes_.size() && count<=bytes_.size()-static_cast<std::size_t>(start),"fixture_journal_read");return Bytes(bytes_.begin()+static_cast<std::size_t>(start),bytes_.begin()+static_cast<std::size_t>(start)+count);}
};
class Writer {
    GptFixturePort& port_;j::Bindings bindings_;j::Digest header_{},last_{};j::Identity publisher_{};std::uint64_t epoch_=0,sequence_=0;Bytes bytes_;
public:
    Writer(GptFixturePort& port,const j::Bindings& binding):port_(port),bindings_(binding),publisher_(identity(text(port.manifest(),"publisher_identity"))),epoch_(integer(text(port.manifest(),"publisher_epoch"))) {}
    void persist(const Bytes& data) {
        require(bytes_.size()+data.size()<=1048576,"fixture_journal_budget");port_.check_ownership();port_.append_journal(data);port_.flush_journal();auto expected=bytes_;expected.insert(expected.end(),data.begin(),data.end());require(port_.read_journal()==expected,"fixture_journal_reread");bytes_=std::move(expected);port_.check_ownership();
    }
    void start() {const auto raw=j::encode_header(bindings_);persist(raw);std::copy_n(raw.begin()+160,32,header_.begin());last_=header_;}
    void append(std::uint16_t kind,const V& payload) {
        require(sequence_<32,"fixture_record_budget");j::Record r;r.kind=kind;r.flags=1;r.sequence=sequence_+1;r.publisher=publisher_;r.publisher_epoch=epoch_;r.previous=last_;r.payload=bytes(json::dump(payload));const auto raw=j::encode_record(header_,r);persist(raw);std::copy_n(raw.end()-32,32,last_.begin());++sequence_;
    }
};
V report(const char* status,std::size_t completed,bool possible,const char* diagnostic="") {
    return V::object().put("schema",V::string("org.disked.gpt-fixture-execution-result/1")).put("status",V::string(status)).put("completed_patches",exact(completed)).put("possible_image_effects",V::boolean_value(possible)).put("diagnostic",V::string(diagnostic)).put("fixture_only",V::boolean_value(true)).put("product_writes_admitted",V::boolean_value(false)).put("storage_independent",V::boolean_value(false)).put("qualifies_power_loss",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));
}
}
GptFixtureExecution::GptFixtureExecution(const p::GptRepairCapture& basis,const std::string& expected,const p::GptRepairSelection& source):basis_(basis),plan_(basis,expected,source),backup_(backup(basis,plan_)) {
    require((basis.block_bytes==512 || basis.block_bytes==4096) && multiply(basis.blocks,basis.block_bytes)<=8388608,"fixture_image_budget");
}
V GptFixtureExecution::prepare(const V& m) const {
    manifest_shape(m,multiply(basis_.blocks,basis_.block_bytes));return V::object().put("phase",V::string("prepared")).put("manifest",m).put("manifest_digest",V::string(hash(m))).put("definition",plan_.definition()).put("plan_digest",V::string(plan_.digest())).put("backup_digest",V::string(hash(backup_))).put("backup_bytes",exact(backup_.size())).put("execution_authorized",V::boolean_value(false));
}
V GptFixtureExecution::execute(GptFixturePort& port,const V& review,const V& grant,const std::string& cancel) const {
    std::size_t completed=0;bool possible=false;
    try {
        require(cancel=="none" || cancel=="before-effects" || cancel=="after-first-patch","fixture_cancellation");prepare(port.manifest());validate_receipts(port.manifest(),plan_,review,grant);port.check_ownership();
        require(plan_.matches_capture(recapture(port,basis_)),"fixture_basis_changed");require(port.read_backup().empty() && port.read_journal().empty(),"fixture_attempt_already_started");
        if(plan_.patches().empty())return report("unchanged",0,false);
        if(cancel=="before-effects")return report("cancelled_before_effects",0,false);
        port.write_backup(backup_);port.flush_backup();require(port.read_backup()==backup_,"fixture_backup_reread");
        require(plan_.matches_capture(recapture(port,basis_)),"fixture_basis_changed");Writer log(port,bindings(port.manifest(),plan_));log.start();log.append(1,plan_.definition());log.append(2,review);log.append(3,grant);log.append(4,admission(port.manifest(),plan_,backup_,review,grant));
        for(std::size_t i=0;i<plan_.patches().size();++i) {
            const auto before=overlay(basis_,plan_,i);const auto before_digest=p::gpt_repair_capture_digest(before);require(p::gpt_repair_capture_digest(recapture(port,basis_))==before_digest,"fixture_prefix_changed");
            log.append(5,event(plan_,backup_,"intention",i,before_digest));port.check_ownership();possible=true;const auto& patch=plan_.patches()[i];port.write_image(patch.offset,patch.after);port.flush_image();
            const auto after_digest=p::gpt_repair_capture_digest(overlay(basis_,plan_,i+1));require(p::gpt_repair_capture_digest(recapture(port,basis_))==after_digest,"fixture_target_reread");log.append(6,event(plan_,backup_,"completion",i+1,after_digest));++completed;
            if(cancel=="after-first-patch") {log.append(7,event(plan_,backup_,"cancellation",completed,after_digest));log.append(9,event(plan_,backup_,"seal-cancelled",completed,after_digest));return report(completed==plan_.patches().size()?"cancelled_after_complete":"cancelled_partial",completed,possible);}
        }
        const auto final_digest=p::gpt_repair_capture_digest(overlay(basis_,plan_,completed));log.append(9,event(plan_,backup_,"seal-completed",completed,final_digest));return report("completed",completed,possible);
    }catch(const std::exception& error) {return report(possible?"unresolved":"refused",completed,possible,error.what());}
}
V GptFixtureExecution::inspect(GptFixturePort& port,const V& review,const V& grant) const {
    prepare(port.manifest());validate_receipts(port.manifest(),plan_,review,grant);port.check_ownership();const auto capture=recapture(port,basis_);const auto observed=p::gpt_repair_capture_digest(capture);auto matches=V::array();
    for(std::size_t i=0;i<=plan_.patches().size();++i)if(observed==p::gpt_repair_capture_digest(overlay(basis_,plan_,i)))matches.items.push_back(exact(i));
    auto states=V::array();for(const auto& patch:plan_.patches()) {
        const auto raw=port.read_image(patch.offset,patch.before.size());std::string state="other";
        if(raw==patch.before)state="before";else if(raw==patch.after)state="after";else if(raw.size()==patch.before.size()) {bool mixed=true;for(std::size_t i=0;i<raw.size();++i)mixed=mixed && (raw[i]==patch.before[i] || raw[i]==patch.after[i]);if(mixed)state="mixed";}
        states.items.push_back(V::object().put("id",V::string(patch.id)).put("state",V::string(state)).put("sha256",V::string(hash(raw))));
    }
    const auto retained=port.read_backup();const auto raw=port.read_journal();Buffer source(raw);const auto binding=bindings(port.manifest(),plan_);std::size_t bootstrap=0,completed=0;bool pending=false,cancelled=false,sealed=false;std::string outcome;
    auto scan=j::scan(source,binding,[&](const j::Record& record) {
        if(record.publisher!=identity(text(port.manifest(),"publisher_identity")) || record.publisher_epoch!=integer(text(port.manifest(),"publisher_epoch")))return false;
        V value;try {value=json::parse(std::string(record.payload.begin(),record.payload.end()));if(bytes(json::dump(value))!=record.payload)return false;}catch(const json::Error&) {return false;}
        if(bootstrap<4) {
            const std::vector<V> expected{plan_.definition(),review,grant,admission(port.manifest(),plan_,backup_,review,grant)};
            if(record.kind!=bootstrap+1 || json::dump(value)!=json::dump(expected[bootstrap]))return false;++bootstrap;return true;
        }
        std::string name;std::size_t index=completed;
        if(record.kind==5) {if(pending || cancelled || completed>=plan_.patches().size())return false;name="intention";}
        else if(record.kind==6) {if(!pending || cancelled || completed>=plan_.patches().size())return false;name="completion";index=completed+1;}
        else if(record.kind==7) {if(pending || cancelled || !completed)return false;name="cancellation";}
        else if(record.kind==9) {if(pending || (!cancelled && completed!=plan_.patches().size()))return false;name=cancelled?"seal-cancelled":"seal-completed";}
        else return false;
        const auto wanted=event(plan_,backup_,name,index,p::gpt_repair_capture_digest(overlay(basis_,plan_,index)));if(json::dump(value)!=json::dump(wanted))return false;
        if(record.kind==5)pending=true;else if(record.kind==6){pending=false;++completed;}else if(record.kind==7)cancelled=true;else {sealed=true;outcome=name;}return true;
    });
    const bool backup_ok=retained==backup_,current_matches=std::any_of(matches.items.begin(),matches.items.end(),[completed](const V& v){return v.text==std::to_string(completed);});
    const bool consistent_seal=sealed && scan.disposition=="valid_prefix" && backup_ok && current_matches;
    return V::object().put("schema",V::string("org.disked.gpt-fixture-inspection/1")).put("capture_digest",V::string(observed)).put("matching_prefixes",matches).put("patch_states",states)
        .put("backup_exact",V::boolean_value(backup_ok)).put("backup_bytes",exact(retained.size())).put("backup_sha256",V::string(hash(retained)))
        .put("journal",V::object().put("disposition",V::string(scan.disposition)).put("diagnostic",V::string(scan.diagnostic)).put("records",exact(scan.records)).put("verified_bytes",exact(scan.verified_bytes)).put("error_offset",exact(scan.error_offset)).put("bootstrap_records",exact(bootstrap)).put("confirmed_prefix",exact(completed)).put("pending_intention",V::boolean_value(pending)).put("sealed",V::boolean_value(sealed)).put("outcome",V::string(outcome)))
        .put("current_matches_seal",V::boolean_value(consistent_seal)).put("recovery_required",V::boolean_value(!consistent_seal || completed!=plan_.patches().size())).put("fixture_only",V::boolean_value(true)).put("authorizes_effects",V::boolean_value(false)).put("qualifies_power_loss",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));
}
}}}
