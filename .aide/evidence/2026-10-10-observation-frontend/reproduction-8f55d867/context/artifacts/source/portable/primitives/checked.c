#include "checked.h"
#include <string.h>

int de_u64_parse(const char *text, size_t length, de_u64 *out)
{
    de_u64 candidate = {{0, 0, 0, 0}};
    size_t i;
    unsigned int part;
    de_u32 carry, next;
    if (!length || (length > 1 && text[0] == '0')) return DE_INVALID;
    for (i = 0; i < length; ++i)
        if (text[i] < '0' || text[i] > '9') return DE_INVALID;
    if (length > 20) return DE_OVERFLOW;
    for (i = 0; i < length; ++i) {
        carry = (de_u32)(text[i] - '0');
        for (part = 0; part < 4; ++part) {
            next = (de_u32)candidate.limb[part] * 10 + carry;
            candidate.limb[part] = (unsigned short)(next & 65535UL);
            carry = next >> 16;
        }
        if (carry) return DE_OVERFLOW;
    }
    *out = candidate;
    return DE_OK;
}

int de_u64_format(const de_u64 *value, char *out, size_t capacity)
{
    de_u64 remaining = *value;
    char reverse[20];
    size_t length = 0, i;
    int part, nonzero;
    de_u32 remainder, current;
    do {
        remainder = 0;
        nonzero = 0;
        for (part = 3; part >= 0; --part) {
            current = (remainder << 16) | remaining.limb[part];
            remaining.limb[part] = (unsigned short)(current / 10);
            remainder = current % 10;
            if (remaining.limb[part]) nonzero = 1;
        }
        reverse[length++] = (char)('0' + remainder);
    } while (nonzero);
    if (capacity <= length) return DE_BUFFER;
    for (i = 0; i < length; ++i) out[i] = reverse[length - i - 1];
    out[length] = '\0';
    return DE_OK;
}

int de_u64_add(const de_u64 *a, const de_u64 *b, de_u64 *out)
{
    de_u64 candidate;
    de_u32 carry = 0, sum;
    unsigned int part;
    for (part = 0; part < 4; ++part) {
        sum = (de_u32)a->limb[part] + b->limb[part] + carry;
        candidate.limb[part] = (unsigned short)(sum & 65535UL);
        carry = sum >> 16;
    }
    if (carry) return DE_OVERFLOW;
    *out = candidate;
    return DE_OK;
}

int de_u64_to_u32(const de_u64 *value, de_u32 *out)
{
    if (value->limb[2] || value->limb[3]) return DE_WIDTH;
    *out = ((de_u32)value->limb[1] << 16) | value->limb[0];
    return DE_OK;
}

int de_u64_compare(const de_u64 *a, const de_u64 *b)
{
    int part;
    for (part = 3; part >= 0; --part) {
        if (a->limb[part] < b->limb[part]) return -1;
        if (a->limb[part] > b->limb[part]) return 1;
    }
    return 0;
}

/* Return the borrow; use only with an already checked range or explicit high bit. */
static de_u32 subtract(const de_u64 *a, const de_u64 *b, de_u64 *out)
{
    de_u32 borrow = 0, subtrahend, minuend;
    unsigned int part;
    for (part = 0; part < 4; ++part) {
        minuend = a->limb[part]; subtrahend = (de_u32)b->limb[part] + borrow;
        out->limb[part] = (unsigned short)((minuend - subtrahend) & 65535UL);
        borrow = minuend < subtrahend;
    }
    return borrow;
}

int de_u64_sub(const de_u64 *a, const de_u64 *b, de_u64 *out)
{
    de_u64 candidate;
    if (subtract(a, b, &candidate)) return DE_UNDERFLOW;
    *out = candidate;
    return DE_OK;
}

int de_u64_mul(const de_u64 *a, const de_u64 *b, de_u64 *out)
{
    unsigned short wide[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    de_u64 candidate;
    unsigned int i, j;
    de_u32 carry, sum;
    for (i = 0; i < 4; ++i) {
        carry = 0;
        for (j = 0; j < 4; ++j) {
            /* 65535*65535 + 65535 + 65535 fits exactly in u32. */
            sum = (de_u32)a->limb[i] * b->limb[j] + wide[i + j] + carry;
            wide[i + j] = (unsigned short)(sum & 65535UL); carry = sum >> 16;
        }
        wide[i + 4] = (unsigned short)carry;
    }
    for (i = 4; i < 8; ++i) if (wide[i]) return DE_OVERFLOW;
    for (i = 0; i < 4; ++i) candidate.limb[i] = wide[i];
    *out = candidate;
    return DE_OK;
}

int de_u64_divmod(const de_u64 *a, const de_u64 *b, de_u64 *quotient, de_u64 *remainder)
{
    de_u64 q = {{0, 0, 0, 0}}, r = {{0, 0, 0, 0}}, reduced;
    int bit;
    unsigned int part;
    de_u32 carry, next;
    if (quotient == remainder) return DE_INVALID;
    if (!(b->limb[0] | b->limb[1] | b->limb[2] | b->limb[3])) return DE_DIVZERO;
    for (bit = 63; bit >= 0; --bit) {
        carry = ((de_u32)a->limb[bit / 16] >> (bit % 16)) & 1;
        for (part = 0; part < 4; ++part) {
            next = (de_u32)r.limb[part] * 2 + carry;
            r.limb[part] = (unsigned short)(next & 65535UL); carry = next >> 16;
        }
        if (carry || de_u64_compare(&r, b) >= 0) {
            /* A borrow consumes the explicit 65th remainder bit. */
            subtract(&r, b, &reduced); r = reduced;
            q.limb[bit / 16] |= (unsigned short)((de_u32)1 << (bit % 16));
        }
    }
    *quotient = q; *remainder = r;
    return DE_OK;
}

de_u64 de_u64_from_u32(de_u32 value)
{
    de_u64 result = {{0, 0, 0, 0}};
    result.limb[0] = (unsigned short)(value & 65535UL);
    result.limb[1] = (unsigned short)(value >> 16);
    return result;
}

int de_u64_from_size(size_t value, de_u64 *out)
{
    unsigned char bytes[8];
    unsigned int i;
    for (i = 0; i < 8; ++i) { bytes[i] = (unsigned char)(value & 255U); value >>= 8; }
    if (value) return DE_WIDTH;
    return de_u64_load_le(bytes, 8, out);
}

int de_u64_to_size(const de_u64 *value, size_t *out)
{
    size_t result = 0, maximum = (size_t)-1;
    unsigned char bytes[8];
    int i;
    de_u64_store_le(value, bytes, 8);
    for (i = 7; i >= 0; --i) {
        if (result > maximum / 256U ||
            (result == maximum / 256U && bytes[i] > maximum % 256U)) return DE_WIDTH;
        result = result * 256U + bytes[i];
    }
    *out = result;
    return DE_OK;
}

int de_u64_load_le(const unsigned char *bytes, size_t length, de_u64 *out)
{
    de_u64 candidate;
    unsigned int part;
    if (length != 8) return DE_INVALID;
    for (part = 0; part < 4; ++part)
        candidate.limb[part] = (unsigned short)((de_u32)bytes[2 * part] |
            ((de_u32)bytes[2 * part + 1] << 8));
    *out = candidate;
    return DE_OK;
}

int de_u64_store_le(const de_u64 *value, unsigned char *out, size_t capacity)
{
    unsigned int part;
    if (capacity < 8) return DE_BUFFER;
    for (part = 0; part < 4; ++part) {
        out[2 * part] = (unsigned char)(value->limb[part] & 255U);
        out[2 * part + 1] = (unsigned char)(value->limb[part] >> 8);
    }
    return DE_OK;
}

int de_bytes_escape(const unsigned char *bytes, size_t length, char *out, size_t capacity)
{
    static const char digits[] = "0123456789ABCDEF";
    size_t i, required = 0, position = 0;
    unsigned char byte;
    if (length > 256) return DE_INVALID;
    for (i = 0; i < length; ++i) {
        byte = bytes[i];
        required += byte == '\\' ? 2 : (byte >= 32 && byte <= 126 ? 1 : 4);
    }
    if (capacity <= required) return DE_BUFFER;
    for (i = 0; i < length; ++i) {
        byte = bytes[i];
        if (byte == '\\') { out[position++] = '\\'; out[position++] = '\\'; }
        else if (byte >= 32 && byte <= 126) out[position++] = (char)byte;
        else {
            out[position++] = '\\'; out[position++] = 'x';
            out[position++] = digits[byte >> 4]; out[position++] = digits[byte & 15];
        }
    }
    out[position] = '\0';
    return DE_OK;
}
