#include "exfat-upcase-draft.h"
#include <stdio.h>
#include <string.h>

static int literal_tests(void) {
    static unsigned char bytes[131072];
    static unsigned short mapping[65536];
    de_exfat_upcase state, saved;
    de_exfat_upcase_step step;
    de_view chunk;
    de_u32 i, sum=0, n;
    unsigned short hash;
    unsigned short left[3]={97,98,99},right[3]={65,66,67};
    int equal;
    for(i=0;i<65536UL;++i){n=i;if(n>=97 && n<=122)n-=32;bytes[i*2]=(unsigned char)n;bytes[i*2+1]=(unsigned char)(n>>8);}
    for(i=0;i<131072UL;++i){sum=(sum>>1)|((sum&1)?0x80000000UL:0);sum+=bytes[i];}
    if(de_exfat_upcase_init(131072UL,sum,0,&state))return 1;
    for(i=0;i<131072UL;++i){chunk.data=bytes+i;chunk.size=1;
        if(de_exfat_upcase_feed(&state,&chunk,i,1,1,mapping+state.mapped,65536UL-state.mapped,&step))return 2;
    }
    if(de_exfat_upcase_finish(&state) || !state.valid)return 3;
    if(de_exfat_name_hash(mapping,65536UL,left,3,&hash))return 4;
    if(de_exfat_name_equal(mapping,65536UL,left,3,right,3,&equal)||!equal)return 5;
    saved=state;chunk.data=bytes;chunk.size=1;
    if(de_exfat_upcase_feed(&state,&chunk,131072UL,1,1,mapping,65536UL,&step)!=DE_INVALID || memcmp(&state,&saved,sizeof(state)))return 6;
    printf("literal mapping/hash smoke passed %u\n",(unsigned int)hash);return 0;
}
static int compressed_tests(void) {
    unsigned char bytes[64];
    unsigned short words[32];
    unsigned short mapping[128];
    de_exfat_upcase state,saved;
    de_exfat_upcase_step step;
    de_view chunk;
    de_u32 sum=0,i;unsigned int count=0;
    words[count++]=65535U;words[count++]=97U;
    for(i=65;i<=90;++i)words[count++]=(unsigned short)i;
    words[count++]=65535U;words[count++]=65412U;words[count++]=65535U;
    for(i=0;i<count;++i){bytes[i*2]=(unsigned char)words[i];bytes[i*2+1]=(unsigned char)(words[i]>>8);}
    for(i=0;i<count*2;++i){sum=(sum>>1)|((sum&1)?0x80000000UL:0);sum+=bytes[i];}
    if(de_exfat_upcase_init(count*2,sum,1,&state))return 7;
    chunk.data=bytes;chunk.size=4;saved=state;
    if(de_exfat_upcase_feed(&state,&chunk,0,4,97,mapping,96,&step)!=DE_BUFFER || memcmp(&state,&saved,sizeof(state)))return 8;
    if(de_exfat_upcase_feed(&state,&chunk,0,4,97,mapping,128,&step))return 9;
    chunk.data=bytes+4;chunk.size=52;
    if(de_exfat_upcase_feed(&state,&chunk,4,52,26,mapping,128,&step))return 10;
    chunk.data=bytes+56;chunk.size=4;
    if(de_exfat_upcase_feed(&state,&chunk,56,4,1,mapping,128,&step))return 11;
    chunk.data=0;chunk.size=0;
    while(state.pending_identity)if(de_exfat_upcase_feed(&state,&chunk,state.consumed,0,128,mapping,128,&step))return 12;
    chunk.data=bytes+60;chunk.size=2;
    if(de_exfat_upcase_feed(&state,&chunk,60,2,1,mapping,128,&step) || de_exfat_upcase_finish(&state) || !state.valid)return 13;
    puts("compressed split/run smoke passed");return 0;
}
int main(void){int result=literal_tests();if(!result)result=compressed_tests();return result;}
