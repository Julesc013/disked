#include "gpt_restoration.h"
#include <algorithm>

namespace disked { namespace recovery { namespace proposal {
namespace {
namespace j=journal::proposal;using V=json::Value;using execution::proposal::FixtureError;
[[noreturn]] void fail(const char* code) {throw FixtureError(code);}
void require(bool ok,const char* code) {if(!ok)fail(code);}
std::string text(const V& v,const char* key) {const auto x=v.find(key);require(x && x->kind==V::Kind::string,"restoration_shape");return x->text;}
bool flag(const V& v,const char* key) {const auto x=v.find(key);require(x && x->kind==V::Kind::boolean,"restoration_shape");return x->boolean;}
V exact(std::uint64_t n) {return V::string(std::to_string(n));}
Bytes bytes(const std::string& s) {return Bytes(s.begin(),s.end());}
std::string hex(const unsigned char* data,std::size_t size) {const char d[]="0123456789abcdef";std::string s;for(std::size_t i=0;i<size;++i){s+=d[data[i]>>4];s+=d[data[i]&15];}return s;}
std::string hash(const Bytes& b) {const auto h=j::hash(b);return "sha256:"+hex(h.data(),h.size());}
std::string hash(const V& v) {return hash(bytes(json::dump(v)));}
unsigned digit(char c) {if(c>='0' && c<='9')return static_cast<unsigned>(c-'0');if(c>='a' && c<='f')return static_cast<unsigned>(c-'a'+10);fail("restoration_digest");}
j::Digest parse_digest(const std::string& s) {require(s.size()==71 && s.compare(0,7,"sha256:")==0,"restoration_digest");j::Digest d{};for(std::size_t i=0;i<32;++i)d[i]=static_cast<unsigned char>(digit(s[7+i*2])*16+digit(s[8+i*2]));require(std::any_of(d.begin(),d.end(),[](unsigned char b){return b!=0;}),"restoration_digest");return d;}
j::Identity identity(const std::string& s) {require(s.size()==32,"restoration_identity");j::Identity id{};for(std::size_t i=0;i<16;++i)id[i]=static_cast<unsigned char>(digit(s[i*2])*16+digit(s[i*2+1]));require(std::any_of(id.begin(),id.end(),[](unsigned char b){return b!=0;}),"restoration_identity");return id;}
void closed(const V& v,std::initializer_list<const char*> keys) {require(v.kind==V::Kind::object && v.fields.size()==keys.size(),"restoration_shape");for(const auto key:keys)require(v.find(key),"restoration_shape");}
V ids(const std::vector<planner::proposal::GptRepairPatch>& patches) {auto out=V::array();for(const auto& p:patches)out.items.push_back(V::string(p.id));return out;}
Bytes current(execution::proposal::GptFixturePort& port,std::size_t size) {port.check_ownership();auto b=port.read_image(0,size);require(b.size()==size,"restoration_image_short");port.check_ownership();return b;}
void check_store(const V& m,const V& s,const std::string& name) {
    closed(s,{"schema","name","identity","publisher_identity","publisher_epoch","executor_digest","storage_independent"});require(text(s,"schema")=="org.disked.gpt-restoration-store/1" && text(s,"name")==name && !flag(s,"storage_independent"),"restoration_store_scope");parse_digest(text(s,"identity"));identity(text(s,"publisher_identity"));
    require(json::decimal_u64(text(s,"publisher_epoch")) && std::stoull(text(s,"publisher_epoch"))>0,"restoration_store_identity");require(text(s,"executor_digest")==text(m,"executor_digest"),"restoration_code_generation");
    for(const auto key:{"root_identity","image_identity","backup_identity","journal_identity"})require(text(s,"identity")!=text(m,key),"restoration_store_alias");
}
j::Bindings restoration_bindings(const V& m,const V& s,const std::string& definition_digest) {
    j::Bindings b;const auto id=parse_digest(text(s,"identity"));std::copy_n(id.begin(),16,b.journal.begin());b.plan=parse_digest(definition_digest);
    b.targets=parse_digest(hash(V::object().put("original",m).put("recovery_store",s)));b.providers=parse_digest(hash(V::object().put("provider",*m.find("provider_id")).put("executor",*s.find("executor_digest"))));return b;
}
V restoration_admission(const V& store,const std::string& definition_digest,const V& review,const V& grant) {
    return V::object().put("schema",V::string("org.disked.gpt-restoration-admission/1")).put("restoration_digest",V::string(definition_digest)).put("review_digest",V::string(hash(review))).put("grant_digest",V::string(hash(grant))).put("store",store);
}
class Buffer:public j::Source {
    const Bytes& raw_;
public:
    explicit Buffer(const Bytes& raw):raw_(raw) {}
    std::uint64_t size() override {return raw_.size();}
    Bytes read_at(std::uint64_t offset,std::size_t count) override {require(offset<=raw_.size() && count<=raw_.size()-static_cast<std::size_t>(offset),"restoration_read_extent");return Bytes(raw_.begin()+static_cast<std::size_t>(offset),raw_.begin()+static_cast<std::size_t>(offset)+count);}
};
class Writer {
    GptRestorationPort& port_;j::Bindings bindings_;j::Digest header_{},last_{};j::Identity publisher_{};std::uint64_t epoch_=0,sequence_=0;Bytes persisted_;
public:
    Writer(GptRestorationPort& port,const std::string& definition_digest):port_(port) {
        const auto& s=port.restoration_store();bindings_=restoration_bindings(port.manifest(),s,definition_digest);publisher_=identity(text(s,"publisher_identity"));epoch_=std::stoull(text(s,"publisher_epoch"));
    }
    void persist(const Bytes& data) {require(persisted_.size()+data.size()<=1048576,"restoration_journal_budget");port_.check_ownership();port_.append_journal(data);port_.flush_journal();auto wanted=persisted_;wanted.insert(wanted.end(),data.begin(),data.end());require(port_.read_journal()==wanted,"restoration_journal_reread");persisted_=std::move(wanted);port_.check_ownership();}
    void start() {const auto raw=j::encode_header(bindings_);persist(raw);std::copy_n(raw.begin()+160,32,header_.begin());last_=header_;}
    void append(std::uint16_t kind,const V& value) {require(sequence_<32,"restoration_record_budget");j::Record r;r.kind=kind;r.flags=1;r.sequence=sequence_+1;r.publisher=publisher_;r.publisher_epoch=epoch_;r.previous=last_;r.payload=bytes(json::dump(value));const auto raw=j::encode_record(header_,r);persist(raw);std::copy_n(raw.end()-32,32,last_.begin());++sequence_;}
};
V result(const char* status,std::size_t completed,bool possible,const char* diagnostic="") {return V::object().put("schema",V::string("org.disked.gpt-restoration-result/1")).put("status",V::string(status)).put("completed_patches",exact(completed)).put("possible_image_effects",V::boolean_value(possible)).put("diagnostic",V::string(diagnostic)).put("fixture_only",V::boolean_value(true)).put("product_writes_admitted",V::boolean_value(false)).put("storage_independent",V::boolean_value(false)).put("qualifies_power_loss",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));}
}
GptFixtureRestoration::GptFixtureRestoration(const execution::proposal::GptFixtureExecution& original,const Bytes& seed,execution::proposal::GptFixturePort& readonly,const V& old_review,const V& old_grant,const std::string& attempt):original_(original),basis_(seed),manifest_(readonly.manifest()) {
    require(!seed.empty() && seed.size()<=8388608 && hash(seed)==text(manifest_,"image_before_sha256"),"restoration_original_basis");
    require(attempt.size()==32 && attempt.find_first_not_of("0123456789abcdef")==attempt.npos && attempt!=std::string(32,'0'),"restoration_attempt");
    inspection_=original_.inspect(readonly,old_review,old_grant);backup_=readonly.read_backup();old_journal_=readonly.read_journal();require(backup_==original_.backup_bytes(),"restoration_backup_invalid");observed_=current(readonly,seed.size());
    const auto& history=*inspection_.find("journal");
    if(observed_!=basis_) {
        require(text(history,"disposition")=="valid_prefix" || text(history,"disposition")=="torn_tail","restoration_history_invalid");
        require(text(history,"bootstrap_records")=="4","restoration_history_bootstrap");
        require(!flag(history,"sealed") || (text(history,"outcome")=="seal-cancelled" && std::stoull(text(history,"confirmed_prefix"))<original_.plan().patches().size()),"restoration_completed_operation");
    }
    auto repaired=basis_;for(const auto& p:original_.plan().patches()) {require(p.offset<=seed.size() && p.after.size()<=seed.size()-static_cast<std::size_t>(p.offset),"restoration_extent");std::copy(p.after.begin(),p.after.end(),repaired.begin()+static_cast<std::size_t>(p.offset));}
    for(std::size_t i=0;i<basis_.size();++i)require(observed_[i]==basis_[i] || observed_[i]==repaired[i],"restoration_foreign_bytes");
    auto rows=V::array();for(auto at=original_.plan().patches().rbegin();at!=original_.plan().patches().rend();++at) {
        const auto start=static_cast<std::size_t>(at->offset);Bytes before(observed_.begin()+start,observed_.begin()+start+at->before.size());if(before==at->before)continue;
        planner::proposal::GptRepairPatch p;p.id=at->id;p.offset=at->offset;p.before=std::move(before);p.after=at->before;if(!patches_.empty())p.depends_on.push_back(patches_.back().id);patches_.push_back(std::move(p));
        auto dependencies=V::array();for(const auto& id:patches_.back().depends_on)dependencies.items.push_back(V::string(id));
        rows.items.push_back(V::object().put("id",V::string(at->id)).put("offset",exact(at->offset)).put("bytes",exact(at->before.size())).put("before_sha256",V::string(hash(patches_.back().before))).put("after_sha256",V::string(hash(at->before))).put("depends_on",dependencies));
    }
    definition_=V::object().put("schema",V::string("org.disked.gpt-fixture-restoration/1")).put("scope",V::string("owned-file-fixture")).put("operation",V::string("restore-original-fixture-basis"))
        .put("attempt_id",V::string(attempt)).put("journal_name",V::string("recovery-"+attempt+".bin")).put("original_plan_digest",V::string(original_.plan().digest())).put("original_manifest_digest",V::string(hash(manifest_)))
        .put("original_image_digest",V::string(hash(basis_))).put("observed_image_digest",V::string(hash(observed_))).put("backup_digest",V::string(hash(backup_))).put("original_journal_digest",V::string(hash(old_journal_)))
        .put("inspection_digest",V::string(hash(inspection_))).put("resources",manifest_).put("patches",rows).put("restores_healthy_gpt",V::boolean_value(false)).put("product_writes_admitted",V::boolean_value(false)).put("qualifies_power_loss",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));digest_=hash(definition_);
}
const std::string& GptFixtureRestoration::journal_name() const {return definition_.find("journal_name")->text;}
V GptFixtureRestoration::prepare() const {return V::object().put("phase",V::string("restoration_prepared")).put("definition",definition_).put("restoration_digest",V::string(digest_)).put("original_inspection",inspection_).put("execution_authorized",V::boolean_value(false));}
void GptFixtureRestoration::validate_grant(const V& review,const V& grant) const {
    closed(review,{"schema","restoration_digest","observed_image_digest","reviewed","issuer","evidence_digest"});require(text(review,"schema")=="org.disked.gpt-restoration-review/1" && text(review,"issuer")=="fixture-controller" && flag(review,"reviewed"),"restoration_review");parse_digest(text(review,"evidence_digest"));require(text(review,"restoration_digest")==digest_ && text(review,"observed_image_digest")==text(definition_,"observed_image_digest"),"restoration_review_binding");
    closed(grant,{"schema","restoration_digest","review_digest","original_manifest_digest","executor_digest","patch_ids","allow_fixture_restoration","allow_new_recovery_journal","acknowledge_nonatomic_same_volume"});
    require(text(grant,"schema")=="org.disked.gpt-restoration-grant/1" && flag(grant,"allow_fixture_restoration") && flag(grant,"allow_new_recovery_journal") && flag(grant,"acknowledge_nonatomic_same_volume"),"restoration_grant");
    require(text(grant,"restoration_digest")==digest_ && text(grant,"review_digest")==hash(review) && text(grant,"original_manifest_digest")==hash(manifest_) && text(grant,"executor_digest")==text(manifest_,"executor_digest"),"restoration_grant_binding");require(json::dump(*grant.find("patch_ids"))==json::dump(ids(patches_)),"restoration_grant_scope");
}
V GptFixtureRestoration::execute(GptRestorationPort& port,const V& review,const V& grant) const {
    std::size_t completed=0;bool possible=false;
    try {
        validate_grant(review,grant);require(json::dump(port.manifest())==json::dump(manifest_),"restoration_manifest_changed");check_store(manifest_,port.restoration_store(),journal_name());port.check_ownership();
        require(port.read_backup()==backup_ && port.read_original_journal()==old_journal_,"restoration_artifacts_changed");require(current(port,basis_.size())==observed_,"restoration_snapshot_changed");require(port.read_journal().empty(),"restoration_attempt_already_started");
        if(patches_.empty())return result("unchanged",0,false);
        Writer log(port,digest_);log.start();log.append(1,definition_);log.append(2,review);log.append(3,grant);log.append(4,restoration_admission(port.restoration_store(),digest_,review,grant));
        auto expected=observed_;
        for(std::size_t i=0;i<patches_.size();++i) {
            require(current(port,basis_.size())==expected,"restoration_prefix_changed");require(port.read_backup()==backup_ && port.read_original_journal()==old_journal_,"restoration_artifacts_changed");
            const auto& patch=patches_[i];auto event=V::object().put("schema",V::string("org.disked.gpt-restoration-event/1")).put("restoration_digest",V::string(digest_)).put("event",V::string("intention")).put("prefix",exact(i)).put("image_digest",V::string(hash(expected))).put("patch",definition_.find("patches")->items[i]);log.append(5,event);
            possible=true;port.write_image(patch.offset,patch.after);port.flush_image();std::copy(patch.after.begin(),patch.after.end(),expected.begin()+static_cast<std::size_t>(patch.offset));require(current(port,basis_.size())==expected,"restoration_target_reread");event.put("event",V::string("completion")).put("prefix",exact(i+1)).put("image_digest",V::string(hash(expected)));log.append(6,event);++completed;
        }
        require(expected==basis_ && current(port,basis_.size())==basis_,"restoration_final_basis");require(port.read_backup()==backup_ && port.read_original_journal()==old_journal_,"restoration_artifacts_changed");
        log.append(9,V::object().put("schema",V::string("org.disked.gpt-restoration-event/1")).put("event",V::string("seal-restored-basis")).put("restoration_digest",V::string(digest_)).put("prefix",exact(completed)).put("image_digest",V::string(hash(basis_))));return result("restored_original_basis",completed,possible);
    }catch(const std::exception& error) {return result(possible?"unresolved":"refused",completed,possible,error.what());}
}
V GptFixtureRestoration::inspect(GptRestorationPort& port,const V& review,const V& grant) const {
    validate_grant(review,grant);require(json::dump(port.manifest())==json::dump(manifest_),"restoration_manifest_changed");const auto& store=port.restoration_store();check_store(manifest_,store,journal_name());
    const auto image=current(port,basis_.size()),backup=port.read_backup(),old_history=port.read_original_journal(),raw=port.read_journal();require(raw.size()<=1048576,"restoration_journal_budget");
    auto expected=observed_;auto matches=V::array(),states=V::array();
    for(std::size_t i=0;i<=patches_.size();++i) {if(image==expected)matches.items.push_back(exact(i));if(i<patches_.size()){const auto& p=patches_[i];std::copy(p.after.begin(),p.after.end(),expected.begin()+static_cast<std::size_t>(p.offset));}}
    bool known=true;for(std::size_t i=0;i<image.size();++i)known=known && (image[i]==observed_[i] || image[i]==basis_[i]);
    for(const auto& p:patches_) {
        const auto offset=static_cast<std::size_t>(p.offset);Bytes b(image.begin()+offset,image.begin()+offset+p.before.size());std::string state="other";
        if(b==p.before)state="before";else if(b==p.after)state="after";else {bool mixed=true;for(std::size_t i=0;i<b.size();++i)mixed=mixed && (b[i]==p.before[i] || b[i]==p.after[i]);if(mixed)state="mixed";}
        states.items.push_back(V::object().put("id",V::string(p.id)).put("state",V::string(state)).put("sha256",V::string(hash(b))));
    }
    expected=observed_;std::size_t bootstrap=0,completed=0,records=0;bool pending=false,sealed=false;Buffer source(raw);j::Scan scan;
    if(raw.empty())scan.disposition="not_started";
    else scan=j::scan(source,restoration_bindings(manifest_,store,digest_),[&](const j::Record& record) {
        if(records>=32 || record.publisher!=identity(text(store,"publisher_identity")) || record.publisher_epoch!=std::stoull(text(store,"publisher_epoch")))return false;
        V value;try {value=json::parse(std::string(record.payload.begin(),record.payload.end()));if(bytes(json::dump(value))!=record.payload)return false;}catch(const json::Error&){return false;}
        if(bootstrap<4) {const std::vector<V> values{definition_,review,grant,restoration_admission(store,digest_,review,grant)};if(record.kind!=bootstrap+1 || json::dump(value)!=json::dump(values[bootstrap]))return false;++bootstrap;++records;return true;}
        V wanted;auto after=expected;
        if(record.kind==5 || record.kind==6) {
            if(completed>=patches_.size() || (record.kind==5?pending:!pending))return false;
            if(record.kind==6){const auto& p=patches_[completed];std::copy(p.after.begin(),p.after.end(),after.begin()+static_cast<std::size_t>(p.offset));}
            wanted=V::object().put("schema",V::string("org.disked.gpt-restoration-event/1")).put("restoration_digest",V::string(digest_)).put("event",V::string(record.kind==5?"intention":"completion")).put("prefix",exact(completed+(record.kind==6?1:0))).put("image_digest",V::string(hash(after))).put("patch",definition_.find("patches")->items[completed]);
        }else if(record.kind==9) {
            if(pending || completed!=patches_.size() || expected!=basis_)return false;
            wanted=V::object().put("schema",V::string("org.disked.gpt-restoration-event/1")).put("event",V::string("seal-restored-basis")).put("restoration_digest",V::string(digest_)).put("prefix",exact(completed)).put("image_digest",V::string(hash(basis_)));
        }else return false;
        if(json::dump(value)!=json::dump(wanted))return false;
        if(record.kind==5)pending=true;else if(record.kind==6){pending=false;++completed;expected=std::move(after);}else sealed=true;++records;return true;
    });
    const bool backup_ok=backup==backup_,old_ok=old_history==old_journal_,current_match=image==expected;
    require(current(port,basis_.size())==image,"restoration_inspection_snapshot_changed");port.check_ownership();
    return V::object().put("schema",V::string("org.disked.gpt-restoration-inspection/1")).put("restoration_digest",V::string(digest_)).put("image_digest",V::string(hash(image))).put("matching_prefixes",matches).put("patch_states",states)
        .put("current_known_bytes",V::boolean_value(known)).put("current_original_image",V::boolean_value(image==basis_)).put("backup_exact",V::boolean_value(backup_ok)).put("backup_sha256",V::string(hash(backup))).put("original_journal_unchanged",V::boolean_value(old_ok)).put("original_journal_sha256",V::string(hash(old_history)))
        .put("current_matches_seal",V::boolean_value(sealed && scan.disposition=="valid_prefix" && backup_ok && old_ok && current_match)).put("reconciliation_required",V::boolean_value(!(sealed && scan.disposition=="valid_prefix" && backup_ok && old_ok && current_match)))
        .put("journal",V::object().put("disposition",V::string(scan.disposition)).put("diagnostic",V::string(scan.diagnostic)).put("records",exact(scan.records)).put("verified_bytes",exact(scan.verified_bytes)).put("error_offset",exact(scan.error_offset)).put("bootstrap_records",exact(bootstrap)).put("confirmed_prefix",exact(completed)).put("pending_intention",V::boolean_value(pending)).put("sealed",V::boolean_value(sealed)))
        .put("fixture_only",V::boolean_value(true)).put("authorizes_effects",V::boolean_value(false)).put("product_writes_admitted",V::boolean_value(false)).put("qualifies_power_loss",V::boolean_value(false)).put("qualifies_recovery",V::boolean_value(false));
}
GptFixtureRestoration retained_gpt_restoration(const execution::proposal::GptFixtureExecution& original,const Bytes& seed,const Bytes& observed,const Bytes& old_journal,const V& manifest,const V& old_review,const V& old_grant,const V& definition,const std::string& expected_digest) {
    require(seed.size()==observed.size() && seed.size()<=8388608 && old_journal.size()<=1048576,"restoration_retained_budget");parse_digest(expected_digest);
    class Observation final:public execution::proposal::GptFixturePort {
        const Bytes& image_;const Bytes& backup_;const Bytes& journal_;const V& manifest_;
    public:
        Observation(const Bytes& image,const Bytes& backup,const Bytes& journal,const V& manifest):image_(image),backup_(backup),journal_(journal),manifest_(manifest) {}
        const V& manifest() const override {return manifest_;}
        void check_ownership() override {} // Retained values only; no current resource claim.
        Bytes read_image(std::uint64_t start,std::size_t count) override {require(start<=image_.size() && count<=image_.size()-static_cast<std::size_t>(start),"restoration_retained_extent");return Bytes(image_.begin()+static_cast<std::size_t>(start),image_.begin()+static_cast<std::size_t>(start)+count);}
        Bytes read_backup() override {return backup_;}Bytes read_journal() override {return journal_;}
        void write_image(std::uint64_t,const Bytes&) override {fail("restoration_inspection_read_only");}void flush_image() override {fail("restoration_inspection_read_only");}
        void write_backup(const Bytes&) override {fail("restoration_inspection_read_only");}void flush_backup() override {fail("restoration_inspection_read_only");}
        void append_journal(const Bytes&) override {fail("restoration_inspection_read_only");}void flush_journal() override {fail("restoration_inspection_read_only");}
    } observation(observed,original.backup_bytes(),old_journal,manifest);
    GptFixtureRestoration value(original,seed,observation,old_review,old_grant,text(definition,"attempt_id"));require(value.digest()==expected_digest && json::dump(value.definition())==json::dump(definition),"restoration_retained_binding");return value;
}
}}}
