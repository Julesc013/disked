#include "checked.h"
#include "view.h"
#include "extent.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>

int main() {
    SYSTEM_INFO info{};GetSystemInfo(&info);
    auto* pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,2*info.dwPageSize,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    if(!pages)return 1;
    DWORD old=0;
    if(!VirtualProtect(pages+info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old))return 2;
    auto* last=pages+info.dwPageSize-8;
    for(unsigned i=0;i<8;++i)last[i]=static_cast<unsigned char>(i+1);
    de_view view{},part{};de_u64 value{},expected{};
    if(de_view_init(last,8,&view) || de_view_read_uint(&view,0,8,DE_BIG_ENDIAN,&value))return 3;
    if(de_u64_parse("72623859790382856",17,&expected) || de_u64_compare(&value,&expected))return 4;
    if(de_view_read_uint(&view,1,8,DE_LITTLE_ENDIAN,&value)!=DE_BOUNDS || de_u64_compare(&value,&expected))return 5;
    if(de_view_slice(&view,8,0,&part) || part.data!=pages+info.dwPageSize || part.size)return 6;
    if(de_view_slice(&view,static_cast<size_t>(-1),1,&part)!=DE_BOUNDS)return 7;
    if(!VirtualProtect(pages,info.dwPageSize,PAGE_READONLY,&old))return 8;
    de_buffer buffer{last,8};
    if(de_buffer_write_uint(&buffer,1,8,DE_LITTLE_ENDIAN,&value)!=DE_BOUNDS)return 9;
    if(de_buffer_write_uint(&buffer,0,1,DE_LITTLE_ENDIAN,&value)!=DE_WIDTH)return 10;
    de_block_space space{};de_block_extent extent{};de_byte_extent bytes{};
    auto blocks=de_u64_from_u32(10),start=de_u64_from_u32(9),length=de_u64_from_u32(1);
    if(de_space_init("guard-fixture",13,&blocks,520,&space) || de_extent_make(&space,&start,&length,&extent) || de_extent_to_bytes(&extent,&bytes))return 11;
    auto end=de_u64_from_u32(5200);
    if(de_u64_compare(&bytes.end,&end))return 12;
    if(!VirtualFree(pages,0,MEM_RELEASE))return 13;
    std::puts("C/C++ linkage and actual read-only/no-access page boundaries passed.");return 0;
}
