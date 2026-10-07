#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "file_capture.h"
#include "map_observation.h"
#include <cstdio>

int wmain(int argc,wchar_t** argv) {
    using disked::json::Value;
    try {
        if(argc!=3)return 2;
        const std::wstring path=argv[1],unit_text=argv[2];
        std::uint32_t unit=unit_text==L"512"?512:unit_text==L"4096"?4096:0;
        const auto size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path.data(),static_cast<int>(path.size()),nullptr,0,nullptr,nullptr);
        if(size<=0)return 2;std::string input(static_cast<std::size_t>(size),'\0');
        if(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path.data(),static_cast<int>(path.size()),&input[0],size,nullptr,nullptr)!=size)return 2;
        auto result=disked::capture_raw_image(input,unit);
        // The source and region/workspace buffers have already been released.
        auto value=Value::object().put("report",std::move(result.report)).put("region_manifest",std::move(result.region_manifest));
        disked::json::Limits limits;limits.bytes=320*1024;limits.values=24576;
        std::puts(disked::json::dump(value,limits).c_str());return 0;
    } catch(const disked::ImageCaptureError& error) {
        const auto out=Value::object().put("refusal",Value::string(error.what())).put("platform_code",Value::string(std::to_string(error.platform_code)));
        std::puts(disked::json::dump(out).c_str());return 3;
    } catch(const disked::MapObservationError& error) {
        std::puts(disked::json::dump(Value::object().put("refusal",Value::string(error.what()))).c_str());return 3;
    } catch(const std::exception& error) {std::fprintf(stderr,"%s\n",error.what());return 4;}
}
