/* A bounded test transport, not the DiskEd command interpreter. */
#include "checked.h"
#include "view.h"
#include "extent.h"
#include <stdio.h>
#include <string.h>

static const char *status_name(int status)
{
    static const char *names[] = {"ok", "invalid", "overflow", "buffer", "width",
        "underflow", "divzero", "bounds", "empty", "unit", "space", "alignment"};
    return names[status];
}
static int checked(int status, const void *after, const void *before, size_t size)
{
    if (!status) return 0;
    if (memcmp(after, before, size)) { puts("BUG changed_on_refusal"); return -1; }
    printf("refused %s\n", status_name(status)); return 1;
}
static void number(const de_u64 *value)
{
    char text[21];
    de_u64_format(value, text, sizeof(text)); printf("%s", text);
}
static void hex(const unsigned char *data, size_t size)
{
    size_t i;
    for (i = 0; i < size; ++i) printf("%02x", (unsigned int)data[i]);
}
static int selftest(void)
{
    de_u64 zero = {{0,0,0,0}}, one = {{1,0,0,0}}, a, b, q, r, before;
    de_block_space space, bad, space_before;
    de_block_extent extent, extent_before;
    de_view view, view_before;
    int flag = 19;
    memset(&q,0x5a,sizeof(q)); before=q; r=q;
    if (de_u64_divmod(&one,&zero,&q,&r)!=DE_DIVZERO || memcmp(&q,&before,sizeof(q)) || memcmp(&r,&before,sizeof(r))) return 1;
    if (de_u64_divmod(&one,&one,&q,&q)!=DE_INVALID || memcmp(&q,&before,sizeof(q))) return 2;
    a=de_u64_from_u32(37); b=de_u64_from_u32(5);
    if (de_u64_divmod(&a,&b,&a,&b) || a.limb[0]!=7 || b.limb[0]!=2) return 3;
    a=de_u64_from_u32(7); b=de_u64_from_u32(6);
    if (de_u64_mul(&a,&b,&a) || a.limb[0]!=42 || de_u64_sub(&a,&b,&b) || b.limb[0]!=36) return 4;
    memset(&view,0x5a,sizeof(view)); memcpy(&view_before,&view,sizeof(view));
    if (de_view_init(NULL,1,&view)!=DE_INVALID || memcmp(&view,&view_before,sizeof(view))) return 5;
    if (de_view_init(NULL,0,&view) || de_view_slice(&view,0,0,&view) || view.data || view.size) return 6;
    memcpy(&view_before,&view,sizeof(view));
    if (de_view_slice(&view,(size_t)-1,1,&view)!=DE_BOUNDS || memcmp(&view,&view_before,sizeof(view))) return 7;
    memset(&space,0x5a,sizeof(space)); memcpy(&space_before,&space,sizeof(space));
    if (de_space_init("",0,&one,512,&space)!=DE_INVALID || memcmp(&space,&space_before,sizeof(space))) return 8;
    if (de_space_init("a\0b",3,&one,512,&space)!=DE_INVALID || memcmp(&space,&space_before,sizeof(space))) return 9;
    if (de_space_init("fixture",7,&one,512,&space)) return 10;
    if (de_extent_make(&space,&zero,&one,&extent)) return 11;
    bad=space; bad.logical_block_bytes=0; extent.space=&bad;
    if (de_extent_length(&extent,&q)!=DE_UNIT || memcmp(&q,&before,sizeof(q))) return 12;
    extent.space=&space; extent.start=one; extent.end=zero;
    if (de_extent_overlap(&extent,&extent,&flag)!=DE_EMPTY || flag!=19) return 13;
    memset(&extent,0x5a,sizeof(extent)); memcpy(&extent_before,&extent,sizeof(extent));
    if (de_extent_make(&space,&zero,&zero,&extent)!=DE_EMPTY || memcmp(&extent,&extent_before,sizeof(extent))) return 14;
    puts("ok unchanged_outputs_aliases_invalid_objects"); return 0;
}
static int execute(int argc, char **argv)
{
    de_u64 values[8], q, r, before, rbefore;
    de_block_space space, second_space, space_before;
    de_block_extent extent, second, extent_before;
    de_byte_extent bytes, bytes_before;
    de_view view, slice, slice_before;
    de_buffer buffer;
    unsigned char data[66], saved[66];
    de_u32 unit, width, order, size32, same;
    size_t offset, length;
    unsigned int i;
    int status, result, overlap, contains;
    if (argc==1 && !strcmp(argv[0],"selftest")) return selftest();
    if (argc<2 || argc>9) return 90;
    for (i=1;i<(unsigned int)argc;++i) {
        status=de_u64_parse(argv[i],strlen(argv[i]),&values[i-1]);
        if (status) {printf("refused %s\n",status_name(status));return 0;}
    }
    memset(&q,0x5a,sizeof(q));before=q;memset(&r,0x5a,sizeof(r));rbefore=r;
    if (argc==2 && !strcmp(argv[0],"size")) {
        offset=37;status=de_u64_to_size(&values[0],&offset);
        if (status) {if(offset!=37)return 91;printf("refused %s\n",status_name(status));return 0;}
        if (de_u64_from_size(offset,&q)) return 92;
        printf("ok ");number(&q);putchar('\n');return 0;
    }
    if (argc==3 && (!strcmp(argv[0],"add") || !strcmp(argv[0],"sub") || !strcmp(argv[0],"mul") || !strcmp(argv[0],"div"))) {
        if (!strcmp(argv[0],"add")) status=de_u64_add(&values[0],&values[1],&q);
        else if (!strcmp(argv[0],"sub")) status=de_u64_sub(&values[0],&values[1],&q);
        else if (!strcmp(argv[0],"mul")) status=de_u64_mul(&values[0],&values[1],&q);
        else status=de_u64_divmod(&values[0],&values[1],&q,&r);
        if (status && memcmp(&r,&rbefore,sizeof(r))) return 93;
        result=checked(status,&q,&before,sizeof(q));if(result)return result<0?94:0;
        printf("ok ");number(&q);if (!strcmp(argv[0],"div")){putchar(' ');number(&r);}putchar('\n');return 0;
    }
    if ((argc==5 && (!strcmp(argv[0],"extent") || !strcmp(argv[0],"inclusive"))) ||
        (argc==3 && !strcmp(argv[0],"spacebytes")) || (argc==8 && !strcmp(argv[0],"overlap"))) {
        status=de_u64_to_u32(&values[1],&unit);
        if(status){printf("refused %s\n",status_name(status));return 0;}
        memset(&space,0x5a,sizeof(space));memcpy(&space_before,&space,sizeof(space));
        status=!strcmp(argv[0],"spacebytes") ? de_space_from_bytes("fixture",7,&values[0],unit,&space) :
            de_space_init("fixture",7,&values[0],unit,&space);
        result=checked(status,&space,&space_before,sizeof(space));if(result)return result<0?95:0;
        if(argc==3){printf("ok ");number(&space.blocks);putchar('\n');return 0;}
        memset(&extent,0x5a,sizeof(extent));memcpy(&extent_before,&extent,sizeof(extent));
        status=!strcmp(argv[0],"inclusive") ? de_extent_from_inclusive(&space,&values[2],&values[3],&extent) :
            de_extent_make(&space,&values[2],&values[3],&extent);
        result=checked(status,&extent,&extent_before,sizeof(extent));if(result)return result<0?96:0;
        if(argc==8){
            status=de_u64_to_u32(&values[6],&same);if(status || same>1)return 97;
            second_space=space;memset(&second,0x5a,sizeof(second));memcpy(&extent_before,&second,sizeof(second));
            status=de_extent_make(same?&space:&second_space,&values[4],&values[5],&second);
            result=checked(status,&second,&extent_before,sizeof(second));if(result)return result<0?98:0;
            overlap=19;contains=19;status=de_extent_overlap(&extent,&second,&overlap);
            if(status){if(overlap!=19)return 99;printf("refused %s\n",status_name(status));return 0;}
            if(de_extent_contains(&extent,&second,&contains))return 100;
            printf("ok %d %d\n",overlap,contains);return 0;
        }
        memset(&bytes,0x5a,sizeof(bytes));memcpy(&bytes_before,&bytes,sizeof(bytes));
        status=de_extent_to_bytes(&extent,&bytes);
        if(status){if(memcmp(&bytes,&bytes_before,sizeof(bytes)))return 101;printf("block ");number(&extent.end);printf(" bytes_refused %s\n",status_name(status));return 0;}
        if(de_extent_length(&extent,&q))return 102;
        printf("ok ");number(&extent.end);putchar(' ');number(&bytes.start);putchar(' ');number(&bytes.end);putchar(' ');number(&q);putchar('\n');return 0;
    }
    for(i=0;i<66;++i)data[i]=0xa5;
    for(i=0;i<64;++i)data[i+1]=(unsigned char)i;
    memcpy(saved,data,sizeof(data));
    if(argc==4 && !strcmp(argv[0],"slice")){
        if(de_u64_to_u32(&values[2],&size32) || size32>64)return 103;
        de_view_init(data+1,(size_t)size32,&view);memset(&slice,0x5a,sizeof(slice));memcpy(&slice_before,&slice,sizeof(slice));
        status=de_view_slice_u64(&view,&values[0],&values[1],&slice);
        result=checked(status,&slice,&slice_before,sizeof(slice));if(result)return result<0?104:0;
        printf("ok %lu ",(unsigned long)slice.size);hex(slice.data,slice.size);putchar('\n');return 0;
    }
    if((argc==5 && !strcmp(argv[0],"read")) || (argc==6 && !strcmp(argv[0],"write"))){
        status=de_u64_to_size(&values[0],&offset);
        if(status){printf("refused %s\n",status_name(status));return 0;}
        if(de_u64_to_u32(&values[1],&width) || de_u64_to_u32(&values[2],&order) || width>16 || order>2)return 105;
        if(de_u64_to_u32(&values[argc-2],&size32) || size32>64)return 106;
        length=(size_t)size32;
        if(argc==5){
            de_view_init(data+1,length,&view);status=de_view_read_uint(&view,offset,(unsigned int)width,(int)order,&q);
            result=checked(status,&q,&before,sizeof(q));if(result)return result<0?107:0;
            printf("ok ");number(&q);putchar('\n');return 0;
        }
        buffer.data=data+1;buffer.size=length;
        status=de_buffer_write_uint(&buffer,offset,(unsigned int)width,(int)order,&values[3]);
        result=checked(status,data,saved,sizeof(data));if(result)return result<0?108:0;
        if(data[0]!=0xa5 || data[65]!=0xa5)return 109;
        printf("ok ");hex(data+1,64);putchar('\n');return 0;
    }
    return 110;
}
int main(int argc, char **argv)
{
    char line[256], *words[10], *cursor;
    int count, result;
    if(argc==2 && !strcmp(argv[1],"profile")) {
        printf("ok char=%u short=%u int=%u long=%u pointer=%u size=%u intermediate=%u\n",
            (unsigned int)CHAR_BIT,(unsigned int)(sizeof(short)*CHAR_BIT),(unsigned int)(sizeof(int)*CHAR_BIT),
            (unsigned int)(sizeof(long)*CHAR_BIT),(unsigned int)(sizeof(void*)*CHAR_BIT),(unsigned int)(sizeof(size_t)*CHAR_BIT),(unsigned int)(sizeof(de_u32)*CHAR_BIT));return 0;
    }
    if(argc!=1)return 111;
    while(fgets(line,sizeof(line),stdin)) {
        if(!strchr(line,'\n'))return 112;
        count=0;cursor=line;
        while(*cursor) {
            while(*cursor && strchr(" \r\n",*cursor))++cursor;
            if(!*cursor)break;
            if(count==10)return 113;
            words[count++]=cursor;
            while(*cursor && !strchr(" \r\n",*cursor))++cursor;
            if(*cursor)*cursor++='\0';
        }
        if(!count)return 113;
        result=execute(count,words);if(result)return result;
    }
    return ferror(stdin)?114:0;
}
