#include "gpt.h"
#include <string.h>

static de_u32 crc_byte(de_u32 state, unsigned char byte)
{
    unsigned int i;
    state ^= (de_u32)byte;
    for (i = 0; i < 8; ++i)
        state = (state >> 1) ^ ((state & 1) ? (de_u32)0xedb88320UL : (de_u32)0);
    return state;
}

int de_gpt_crc32(const de_view *bytes, de_u32 *out)
{
    de_u32 state = (de_u32)0xffffffffUL;
    size_t i;
    if (!bytes || !out || (!bytes->data && bytes->size)) return DE_INVALID;
    for (i = 0; i < bytes->size; ++i) state = crc_byte(state, bytes->data[i]);
    *out = state ^ (de_u32)0xffffffffUL;
    return DE_OK;
}

/* Internal header CRC: caller validated HeaderSize and the four-byte hole. */
de_u32 de_gpt_header_checksum(const de_view *bytes, size_t size)
{
    size_t i;
    de_u32 state = (de_u32)0xffffffffUL;
    for (i = 0; i < size; ++i)
        state = crc_byte(state, (i >= 16 && i < 20) ? 0 : bytes->data[i]);
    return state ^ (de_u32)0xffffffffUL;
}

int de_gpt_guid_text(const de_view *bytes, char *out, size_t capacity)
{
    static const unsigned char order[16] = {3,2,1,0,5,4,7,6,8,9,10,11,12,13,14,15};
    static const char digits[] = "0123456789abcdef";
    char value[37];
    unsigned int i, n = 0;
    unsigned char byte;
    if (!bytes || !out || !bytes->data) return DE_INVALID;
    if (bytes->size != 16) return DE_BOUNDS;
    if (capacity < sizeof(value)) return DE_BUFFER;
    for (i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) value[n++] = '-';
        byte = bytes->data[order[i]];
        value[n++] = digits[byte >> 4]; value[n++] = digits[byte & 15];
    }
    value[n] = '\0'; memcpy(out, value, sizeof(value)); return DE_OK;
}

static de_u32 unit16(const unsigned char *bytes)
{
    return (de_u32)bytes[0] | ((de_u32)bytes[1] << 8);
}

int de_gpt_name_utf8(const de_view *bytes, char *out, size_t capacity, int *terminated)
{
    char value[109];
    size_t i, n = 0;
    de_u32 point, low;
    int ended = 0;
    if (!bytes || !out || !terminated || !bytes->data) return DE_INVALID;
    if (bytes->size != 72) return DE_BOUNDS;
    for (i = 0; i < 36; ++i) {
        point = unit16(bytes->data + i * 2);
        if (!point) { ended = 1; break; }
        if (point >= 0xd800UL && point <= 0xdbffUL) {
            if (i + 1 == 36) return DE_INVALID;
            low = unit16(bytes->data + (++i) * 2);
            if (low < 0xdc00UL || low > 0xdfffUL) return DE_INVALID;
            point = (de_u32)0x10000UL + ((point - (de_u32)0xd800UL) << 10) + low - (de_u32)0xdc00UL;
        } else if (point >= 0xdc00UL && point <= 0xdfffUL) return DE_INVALID;
        if (point < 0x80) value[n++] = (char)point;
        else if (point < 0x800) {
            value[n++] = (char)(0xc0 | (point >> 6)); value[n++] = (char)(0x80 | (point & 63));
        } else if (point < 0x10000UL) {
            value[n++] = (char)(0xe0 | (point >> 12)); value[n++] = (char)(0x80 | ((point >> 6) & 63));
            value[n++] = (char)(0x80 | (point & 63));
        } else {
            value[n++] = (char)(0xf0 | (point >> 18)); value[n++] = (char)(0x80 | ((point >> 12) & 63));
            value[n++] = (char)(0x80 | ((point >> 6) & 63)); value[n++] = (char)(0x80 | (point & 63));
        }
    }
    value[n] = '\0';
    if (capacity <= n) return DE_BUFFER;
    memcpy(out, value, n + 1); *terminated = ended; return DE_OK;
}
