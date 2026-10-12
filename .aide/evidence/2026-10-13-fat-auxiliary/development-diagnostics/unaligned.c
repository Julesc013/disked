/* Supplemental MSVC C90 qualification of the exact FAT auxiliary library. */
#include "portable/fat/fat.h"
#include <stdio.h>
#include <string.h>

static void put(unsigned char *p, de_u32 n) {
    size_t i;
    for (i=0;i<4;++i) { p[i]=(unsigned char)(n&255UL);n>>=8; }
}
int main(void) {
    union { de_u32 aligned; unsigned char raw[514]; } buffer;
    unsigned char *p;
    de_view view;
    de_fat_fsinfo info;
    de_fat_header header;
    int bits, status;
    p=buffer.raw+1;
    if (((size_t)p)%sizeof(de_u32)==0) return 1;
    memset(p,0,512);put(p,0x41615252UL);put(p+484,0x61417272UL);
    put(p+488,123);put(p+492,3);put(p+508,0xaa550000UL);
    view.data=p;view.size=512;
    status=de_fat_fsinfo_read(&view,512,65525,&info);
    if (status || info.issues || info.free_count!=123 || info.next_free!=3 || !info.fields_present) return 2;
    for (bits=12;bits<=32;bits=bits==12?16:32) {
        memset(p,255,8);p[0]=0xf8;view.size=bits==12?3:(bits==16?4:8);
        status=de_fat_header_read(&view,bits,0xf8,&header);
        if (status || header.issues || !header.fields_present) return 3;
        if (bits==32) break;
    }
    puts("Unaligned FAT12/16/32 headers and FAT32 FSInfo passed against the native library.");
    return 0;
}
