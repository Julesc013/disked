#include "ntfs.h"
#include <string.h>

int de_ntfs_filename_read(const de_view *raw, unsigned int major, unsigned int minor,
                          de_ntfs_filename *out) {
    de_ntfs_filename value;
    size_t bytes;
    if (!raw || !out || (!raw->data && raw->size) || major != 3 || minor > 1)
        return DE_INVALID;
    memset(&value, 0, sizeof(value));
    value.raw = *raw;
    if (raw->size < 66)
        value.issues = DE_NTFS_NAME_TRUNCATED;
    else {
        value.fields_present = 1;
        de_u64_load_le(raw->data, 8, &value.parent_reference);
        value.parent_record = value.parent_reference;
        value.parent_record.limb[3] = 0;
        value.parent_sequence = value.parent_reference.limb[3];
        value.duplicated_information.data = raw->data + 8;
        value.duplicated_information.size = 56;
        value.name_length = raw->data[64];
        value.namespace_code = raw->data[65];
        value.namespace_known = value.namespace_code <= 3;
        if (!value.namespace_known)
            value.issues |= DE_NTFS_NAME_NAMESPACE;
        if (!value.parent_sequence)
            value.issues |= DE_NTFS_NAME_REFERENCE;
        bytes = (size_t)value.name_length * 2;
        if (!bytes)
            value.issues |= DE_NTFS_NAME_LENGTH;
        if (bytes > raw->size - 66)
            value.issues |= DE_NTFS_NAME_LENGTH | DE_NTFS_NAME_TRUNCATED;
        else {
            value.name.data = raw->data + 66;
            value.name.size = bytes;
            value.suffix.data = value.name.data + bytes;
            value.suffix.size = raw->size - 66 - bytes;
        }
        value.envelope_valid = !(value.issues & (DE_NTFS_NAME_TRUNCATED | DE_NTFS_NAME_LENGTH));
    }
    *out = value;
    return DE_OK;
}
