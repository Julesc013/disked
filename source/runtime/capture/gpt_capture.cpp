#include "gpt_capture.h"
#include "portable/gpt/gpt.h"
#include <algorithm>

namespace disked {
namespace {
using planner::proposal::Bytes;
[[noreturn]] void fail(const char* code) {throw planner::proposal::RepairError(code);}
void checked(int status) {if(status!=DE_OK)fail("repair_offset_overflow");}
de_u64 exact(std::uint64_t n) {de_u64 value{};const auto text=std::to_string(n);checked(de_u64_parse(text.data(),text.size(),&value));return value;}
class Regions {
    const MapRegionReader& reader_;
    const de_block_space& space_;
    std::size_t requests_=0,bytes_=0;
public:
    Regions(const MapRegionReader& reader,const de_block_space& space):reader_(reader),space_(space) {}
    Bytes region(const de_block_extent& blocks) {
        de_byte_extent extent{};checked(de_extent_to_bytes(&blocks,&extent));de_u64 span{};std::size_t length=0;
        checked(de_u64_sub(&extent.end,&extent.start,&span));checked(de_u64_to_size(&span,&length));
        if(requests_>=5 || length>2109440-bytes_)fail("repair_budget");++requests_;bytes_+=length;
        const auto view=reader_(extent);if(view.size>length || (view.size && !view.data))fail("image_region_contract");
        return view.size?Bytes(view.data,view.data+view.size):Bytes{};
    }
    Bytes block(const de_u64& lba) {
        const auto one=de_u64_from_u32(1);de_block_extent extent{};checked(de_extent_make(&space_,&lba,&one,&extent));return region(extent);
    }
    Bytes array(const Bytes& original,const de_u64& lba,int role) {
        de_gpt_header header{};de_view raw{original.data(),original.size()};
        if(de_gpt_header_read(&raw,&space_,&lba,role,&header)!=DE_OK)return {};
        if(header.issues & ~static_cast<de_u32>(DE_GPT_HEADER_CRC))return {};
        Bytes corrected;
        if(header.issues) {
            // Use only the recognizable header's declared extent. Keep original
            // captured bytes for plan identity and repair; never guess layout.
            if(header.header_size<92 || header.header_size>original.size())return {};
            corrected=original;std::fill(corrected.begin()+16,corrected.begin()+20,static_cast<unsigned char>(0));
            de_view prefix{corrected.data(),header.header_size};de_u32 crc=0;checked(de_gpt_crc32(&prefix,&crc));
            for(unsigned i=0;i<4;++i)corrected[16+i]=static_cast<unsigned char>(crc>>(i*8));
            raw={corrected.data(),corrected.size()};
            if(de_gpt_header_read(&raw,&space_,&lba,role,&header)!=DE_OK || !header.consistent)return {};
        }
        const de_gpt_limits limits{1024,4096,1048576};de_block_extent extent{};
        const auto status=de_gpt_request_array(&header,&limits,&extent);
        if(status==DE_BUFFER)fail("repair_budget");if(status!=DE_OK)return {};
        return region(extent);
    }
};
}
planner::proposal::GptRepairCapture capture_gpt_regions(const std::string& id,std::uint64_t epoch,
    std::uint64_t blocks,std::uint32_t unit,const MapRegionReader& reader) {
    if(!reader || !epoch || blocks<3 || (unit!=512 && unit!=4096))fail("image_geometry");
    de_block_space space{};const auto count=exact(blocks);checked(de_space_init(id.data(),id.size(),&count,unit,&space));
    Regions regions(reader,space);planner::proposal::GptRepairCapture out;out.image_id=id;out.epoch=epoch;out.blocks=blocks;out.block_bytes=unit;
    const auto zero=exact(0),one=exact(1),last=exact(blocks-1);
    out.protective_mbr=regions.block(zero);out.primary_header=regions.block(one);out.backup_header=regions.block(last);
    out.primary_array=regions.array(out.primary_header,one,DE_GPT_PRIMARY);
    out.backup_array=regions.array(out.backup_header,last,DE_GPT_BACKUP);
    return out;
}
}
