#include "image_layout_worker.h"
#include "platform/windows/worker_files.h"
#include <set>

namespace disked { namespace nt_inventory {
namespace {
using V=json::Value;namespace w=worker_files;
const V& get(const V& v,const char* k){auto p=v.find(k);if(!p)throw std::invalid_argument("image_layout_worker_shape");return *p;}
std::string text(const V& v,const char* k){const auto& p=get(v,k);if(p.kind!=V::Kind::string)throw std::invalid_argument("image_layout_worker_shape");return p.text;}
std::uint64_t integer(const V& v,const char* k){auto s=text(v,k);if(!json::decimal_u64(s))throw std::invalid_argument("image_layout_worker_integer");return std::stoull(s);}
V number(std::uint64_t n){return V::string(std::to_string(n));}
void exact(const V& v,const std::set<std::string>& keys){if(v.kind!=V::Kind::object || v.fields.size()!=keys.size())throw std::invalid_argument("image_layout_worker_shape");for(const auto& x:v.fields)if(!keys.count(x.first))throw std::invalid_argument("image_layout_worker_shape");}
FileLayoutInput input(const V& h){
    FileLayoutInput r;r.capture_epoch=integer(h,"capture_epoch");const auto& p=get(h,"policy");exact(p,{"partitions","ebr_nodes"});
    const auto parts=integer(p,"partitions"),nodes=integer(p,"ebr_nodes");if(parts>64 || nodes>128)throw std::invalid_argument("image_layout_worker_policy");
    r.policy.partitions=static_cast<unsigned>(parts);r.policy.ebr_nodes=static_cast<unsigned>(nodes);const auto& v=get(h,"provider_input");
    auto keys=std::set<std::string>{"path","unit","expected_source","expected_content_digest","fixture"};for(const auto k:{"startup_fault","reply_fault"})if(v.find(k))keys.insert(k);exact(v,keys);
    r.path=text(v,"path");const auto unit=integer(v,"unit");if(unit>0xffffffffULL)throw std::invalid_argument("image_layout_worker_unit");r.unit=static_cast<std::uint32_t>(unit);
    r.expected_source=get(v,"expected_source");r.expected_content_digest=text(v,"expected_content_digest");r.fixture=get(v,"fixture");validate_file_layout_input(r);
    for(const auto k:{"startup_fault","reply_fault"}){const auto* nested=r.fixture.find(k);const auto* outer=v.find(k);if(bool(nested)!=bool(outer) || (nested && json::dump(*nested)!=json::dump(*outer)))throw std::invalid_argument("image_layout_worker_fixture");}
    return r;
}
V request(const FileLayoutInput& r){
    auto v=V::object().put("path",V::string(r.path)).put("unit",number(r.unit)).put("expected_source",r.expected_source).put("expected_content_digest",V::string(r.expected_content_digest)).put("fixture",r.fixture);
    for(const auto k:{"startup_fault","reply_fault"})if(const auto* p=r.fixture.find(k))v.put(k,*p);
    return V::object().put("capture_epoch",number(r.capture_epoch)).put("policy",V::object().put("partitions",number(r.policy.partitions)).put("ebr_nodes",number(r.policy.ebr_nodes))).put("provider_input",v);
}
std::vector<unsigned char> copy(const V& snapshot,const void* view){
    if(text(snapshot,"status")=="unavailable")return {};
    const auto bytes=integer(get(snapshot,"receipt"),"captured_bytes");if(!view || !bytes || bytes>file_layout_payload_bytes)throw std::invalid_argument("image_layout_worker_payload");
    const auto* start=static_cast<const unsigned char*>(view);return std::vector<unsigned char>(start,start+static_cast<std::size_t>(bytes));
}
ObservationWorkerProfile profile(const void* view=nullptr){
    ObservationWorkerProfile p;p.prefix="image_layout";p.scope="ordinary-local-image-layout";p.input_schema="org.disked.nt-image-layout-worker-input/1";
    p.reply_schema="org.disked.nt-image-layout-worker-reply/1";p.observation_schema="org.disked.nt-image-layout-worker-observation/1";
    p.role=L"__disked_nt_image_layout_fixture_worker";p.attempt_prefix="image-layout-attempt:";p.records_field="layout";
    p.input_mapping_bytes=32768;p.input_limits.bytes=32764;p.input_limits.values=512;p.input_limits.depth=8;p.input_limits.string_bytes=1024;
    p.provider_limits=p.input_limits;p.provider_limits.bytes=8192;p.reply_limits=file_layout_snapshot_limits();p.payload_bytes=file_layout_payload_bytes;
    p.validate_request=[](const V& v){input(v);};p.validate_result=[view](const V& s,const V& h){verify_file_layout_snapshot(s,input(h),copy(s,view));};return p;
}
struct WritableView {
    void* value=nullptr;
    explicit WritableView(HANDLE mapping){value=MapViewOfFile(mapping,FILE_MAP_WRITE,0,0,file_layout_payload_bytes);if(!value)w::fail("image_layout_worker_mapping");}
    ~WritableView(){if(value)UnmapViewOfFile(value);}WritableView(const WritableView&)=delete;WritableView& operator=(const WritableView&)=delete;
};
}
struct ImageLayoutWorker::Impl {
    FileLayoutInput input;w::Handle mapping;void* view=nullptr;std::unique_ptr<ObservationWorker> worker;
    explicit Impl(FileLayoutInput r):input(std::move(r)){}
    ~Impl(){worker.reset();if(view)UnmapViewOfFile(view);}
};
ImageLayoutWorker::ImageLayoutWorker(std::unique_ptr<Impl> p):impl_(std::move(p)){}
ImageLayoutWorker::~ImageLayoutWorker()=default;
std::unique_ptr<ImageLayoutWorker> ImageLayoutWorker::prepare(const FileLayoutInput& r){
    validate_file_layout_input(r);std::unique_ptr<Impl> p(new Impl(r));w::Security security;auto a=security.attributes;
    p->mapping=w::Handle(CreateFileMappingW(INVALID_HANDLE_VALUE,&a,PAGE_READWRITE,0,static_cast<DWORD>(file_layout_payload_bytes),nullptr));if(!p->mapping.valid())w::fail("image_layout_worker_mapping");
    p->view=MapViewOfFile(p->mapping.value,FILE_MAP_READ,0,0,file_layout_payload_bytes);if(!p->view)w::fail("image_layout_worker_mapping");
    p->worker=ObservationWorker::prepare(request(r),profile(p->view),p->mapping.value);return std::unique_ptr<ImageLayoutWorker>(new ImageLayoutWorker(std::move(p)));
}
void ImageLayoutWorker::launch(){impl_->worker->launch();}void ImageLayoutWorker::release(){impl_->worker->release();}void ImageLayoutWorker::cancel(){impl_->worker->cancel();}
bool ImageLayoutWorker::never_launched()const{return impl_->worker->never_launched();}bool ImageLayoutWorker::wait_entered(DWORD n){return impl_->worker->wait_entered(n);}
V ImageLayoutWorker::observe(DWORD n){return impl_->worker->observe(n);}V ImageLayoutWorker::retire(DWORD n){return impl_->worker->retire(n);}
std::shared_ptr<const FileLayoutSnapshot> ImageLayoutWorker::snapshot(){
    const auto observed=observe();if(text(observed,"status")!="completed")return {};const auto& value=get(observed,"result");
    const auto raw=verify_file_layout_snapshot(value,impl_->input,copy(value,impl_->view));if(!raw)return {};auto context=V::object();
    for(const auto k:{"attempt_id","observer_epoch","worker_epoch","request_digest","code_sha256","capture_epoch"})context.put(k,get(observed,k));
    const auto& native=get(observed,"worker");context.put("pid",get(native,"pid")).put("created",get(native,"created")).put("image_profile",V::string("ordinary-image-layout"));
    if(integer(native,"pid")==0 || integer(native,"created")==0)throw std::invalid_argument("image_layout_worker_identity");
    return std::shared_ptr<const FileLayoutSnapshot>(new FileLayoutSnapshot(raw,get(value,"receipt"),std::move(context)));
}
int image_layout_worker_role(int argc,wchar_t** argv){
    return observation_worker_role(argc,argv,profile(),PayloadObservationFactory([](const V& h,const std::function<void()>& notify,HANDLE handle)->ObservationCollector{
        const auto r=input(h);auto view=std::make_shared<WritableView>(handle);notify();
        return [r,view](const std::function<bool()>& stop){
            try{
#ifdef DISKED_FILE_LAYOUT_TESTING
                const auto* p=r.fixture.find("worker_fault");const auto fault=p?p->text:"";if(fault=="hang")for(;;)Sleep(10);if(fault=="late")Sleep(200);
#endif
                auto result=read_file_layout(r,stop);if(result.bytes.size()>file_layout_payload_bytes)throw std::invalid_argument("image_layout_worker_payload");
                std::memcpy(view->value,result.bytes.data(),result.bytes.size());MemoryBarrier();
#ifdef DISKED_FILE_LAYOUT_TESTING
                if(fault=="corrupt_payload")static_cast<unsigned char*>(view->value)[0]^=1;
                if(fault=="corrupt_layout")result.snapshot.fields["layout"].fields["geometry"].put("capacity_bytes",V::string("1"));
                if(fault=="corrupt_receipt")result.snapshot.fields["receipt"].put("path",V::string("forged"));
                if(fault=="claims")result.snapshot.fields["claims"].put("physical_admission",V::boolean_value(true));
#endif
                return result.snapshot;
            }catch(const local_file::Error& e){return file_layout_unavailable(e.what(),e.platform_code);}
             catch(const std::exception& e){return file_layout_unavailable(e.what());}
        };
    }));
}
}}
