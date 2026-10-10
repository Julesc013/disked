#include "checked.h"
#include <stdio.h>
#include <string.h>

static int refuse(int status)
{
    static const char *names[] = {"ok", "invalid", "overflow", "buffer", "width"};
    printf("refused %s\n", names[status]);
    return 2;
}
static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static int unhex(const char *text, unsigned char *out, size_t *count)
{
    size_t length = strlen(text), i;
    int high, low;
    if (length > 512 || length % 2) return DE_INVALID;
    for (i = 0; i < length; i += 2) {
        high = hex_digit(text[i]); low = hex_digit(text[i + 1]);
        if (high < 0 || low < 0) return DE_INVALID;
        out[i / 2] = (unsigned char)(16 * high + low);
    }
    *count = length / 2;
    return DE_OK;
}
static int print_value(const de_u64 *value)
{
    char text[21];
    unsigned char bytes[8];
    unsigned int i;
    if (de_u64_format(value, text, sizeof(text)) ||
        de_u64_store_le(value, bytes, sizeof(bytes))) return 90;
    printf("ok %s ", text);
    for (i = 0; i < 8; ++i) printf("%02x", (unsigned int)bytes[i]);
    putchar('\n');
    return 0;
}
static int selftest(void)
{
    de_u64 value, before, max, one;
    de_u32 narrow = 123;
    char buffer[1025], saved[1025];
    unsigned char bytes[256];
    size_t capacity;
    memset(&value, 0x5a, sizeof(value)); before = value;
    if (de_u64_parse("18446744073709551616", 20, &value) != DE_OVERFLOW ||
        memcmp(&value, &before, sizeof(value))) return 91;
    if (de_u64_parse("1x", 2, &value) != DE_INVALID ||
        memcmp(&value, &before, sizeof(value))) return 92;
    if (de_u64_load_le(bytes, 7, &value) != DE_INVALID ||
        memcmp(&value, &before, sizeof(value))) return 93;
    if (de_u64_parse("18446744073709551615", 20, &max) || de_u64_parse("1", 1, &one)) return 94;
    if (de_u64_add(&max, &one, &value) != DE_OVERFLOW ||
        memcmp(&value, &before, sizeof(value))) return 95;
    if (de_u64_to_u32(&max, &narrow) != DE_WIDTH || narrow != 123) return 96;
    memset(buffer, 0x5a, sizeof(buffer)); memcpy(saved, buffer, sizeof(buffer));
    for (capacity = 0; capacity <= 20; ++capacity)
        if (de_u64_format(&max, buffer, capacity) != DE_BUFFER ||
            memcmp(buffer, saved, sizeof(buffer))) return 97;
    if (de_u64_format(&max, buffer, 21) || strcmp(buffer, "18446744073709551615") || buffer[21] != 0x5a) return 98;
    memset(buffer, 0x5a, sizeof(buffer));
    for (capacity = 0; capacity < 8; ++capacity)
        if (de_u64_store_le(&max, (unsigned char *)buffer, capacity) != DE_BUFFER ||
            memcmp(buffer, saved, sizeof(buffer))) return 99;
    if (de_u64_store_le(&max, (unsigned char *)buffer, 8) || buffer[8] != 0x5a) return 100;
    memset(bytes, 0, sizeof(bytes)); memset(buffer, 0x5a, sizeof(buffer));
    for (capacity = 0; capacity <= 1024; ++capacity)
        if (de_bytes_escape(bytes, 256, buffer, capacity) != DE_BUFFER ||
            memcmp(buffer, saved, sizeof(buffer))) return 101;
    if (de_bytes_escape(bytes, 256, buffer, sizeof(buffer)) || strlen(buffer) != 1024) return 102;
    memset(buffer, 0x5a, sizeof(buffer));
    if (de_bytes_escape(bytes, 257, buffer, sizeof(buffer)) != DE_INVALID ||
        memcmp(buffer, saved, sizeof(buffer))) return 103;
    if (de_u64_add(&one, &one, &one) || de_u64_format(&one, buffer, sizeof(buffer)) || strcmp(buffer, "2")) return 104;
    puts("ok unchanged_outputs_and_bounds");
    return 0;
}
int main(int argc, char **argv)
{
    de_u64 a, b, result;
    de_u32 small;
    unsigned char bytes[256];
    char display[1025];
    size_t length;
    int status;
    if (argc == 2 && !strcmp(argv[1], "profile")) {
        printf("ok char=%u short=%u int=%u long=%u pointer=%u intermediate=%u\n",
            (unsigned int)CHAR_BIT, (unsigned int)(sizeof(short) * CHAR_BIT),
            (unsigned int)(sizeof(int) * CHAR_BIT), (unsigned int)(sizeof(long) * CHAR_BIT),
            (unsigned int)(sizeof(void *) * CHAR_BIT), (unsigned int)(sizeof(de_u32) * CHAR_BIT));
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "selftest")) return selftest();
    if (argc == 3 && (!strcmp(argv[1], "wire") || !strcmp(argv[1], "escape"))) {
        status = unhex(argv[2], bytes, &length);
        if (status) return refuse(status);
        if (!strcmp(argv[1], "wire")) {
            status = de_u64_load_le(bytes, length, &result);
            return status ? refuse(status) : print_value(&result);
        }
        status = de_bytes_escape(bytes, length, display, sizeof(display));
        if (status) return refuse(status);
        printf("ok %s\n", display); return 0;
    }
    if (argc < 3 || argc > 4) return refuse(DE_INVALID);
    status = de_u64_parse(argv[2], strlen(argv[2]), &a);
    if (status) return refuse(status);
    if (argc == 3 && !strcmp(argv[1], "roundtrip")) return print_value(&a);
    if (argc == 3 && !strcmp(argv[1], "narrow")) {
        status = de_u64_to_u32(&a, &small);
        if (status) return refuse(status);
        printf("ok %lu\n", (unsigned long)small); return 0;
    }
    if (argc == 4 && !strcmp(argv[1], "add")) {
        status = de_u64_parse(argv[3], strlen(argv[3]), &b);
        if (status) return refuse(status);
        status = de_u64_add(&a, &b, &result);
        return status ? refuse(status) : print_value(&result);
    }
    return refuse(DE_INVALID);
}
