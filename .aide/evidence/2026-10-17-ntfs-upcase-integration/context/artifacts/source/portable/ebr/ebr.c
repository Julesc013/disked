#include "ebr.h"
#include <string.h>

int de_ebr_init(const de_mbr_table *mbr, unsigned int slot,
                const de_mbr_geometry *geometry, de_ebr_node *nodes,
                size_t capacity, size_t limit, de_ebr_walk *out)
{
    de_ebr_walk value;
    const de_mbr_entry *e;
    if (!mbr || slot >= 4 || !mbr->signature || !nodes || !out ||
        !de_mbr_geometry_valid(geometry) || !limit || limit > DE_EBR_LIMIT || capacity < limit)
        return DE_INVALID;
    e = &mbr->entries[slot];
    if (!e->active || e->kind != DE_MBR_EXTENDED || !e->range_valid) return DE_INVALID;
    memset(&value, 0, sizeof(value));
    value.container = e->extent; value.geometry = *geometry;
    value.nodes = nodes; value.limit = limit; value.pending = e->extent.start;
    value.needs_block = 1; value.issues = mbr->issues;
    *out = value;
    return DE_OK;
}

static void stop(de_ebr_walk *walk, de_u32 issue)
{
    walk->issues |= issue; walk->needs_block = 0; walk->complete = 0;
}

static int includes_lba(const de_block_extent *extent, const de_u64 *lba)
{
    return de_u64_compare(&extent->start, lba) <= 0 && de_u64_compare(lba, &extent->end) < 0;
}

int de_ebr_feed(de_ebr_walk *walk, const de_u64 *lba, const de_view *bytes)
{
    de_mbr_table table;
    de_mbr_entry *data, *link, *earlier;
    de_ebr_node *node;
    size_t i;
    int status, inside, overlap;
    if (!walk || !lba || !bytes || !walk->needs_block || walk->count >= walk->limit ||
        de_u64_compare(lba, &walk->pending)) return DE_INVALID;
    status = de_mbr_decode(bytes, walk->container.space, &table);
    if (status) return status;
    node = &walk->nodes[walk->count];
    node->lba = *lba; node->table = table; ++walk->count;
    /* A requested metadata block can intersect earlier data even if its own
       contents are truncated, unsigned, or unsupported. */
    for (i = 0; i + 1 < walk->count; ++i) {
        earlier = &walk->nodes[i].table.entries[0];
        if (earlier->range_valid && includes_lba(&earlier->extent, lba))
            node->table.issues |= DE_MBR_METADATA;
    }
    walk->issues |= node->table.issues;
    walk->issues |= table.issues;
    if (!table.signature) { stop(walk, table.issues); return DE_OK; }
    data = &node->table.entries[0]; link = &node->table.entries[1];
    if ((data->active && data->kind != DE_MBR_DATA) ||
        (link->active && link->kind != DE_MBR_EXTENDED) ||
        (data->issues & DE_MBR_INACTIVE) || (link->issues & DE_MBR_INACTIVE) ||
        node->table.entries[2].active || node->table.entries[3].active) {
        node->table.issues |= DE_MBR_LAYOUT; stop(walk, DE_MBR_LAYOUT); return DE_OK;
    }
    de_mbr_resolve(walk->container.space, lba, &walk->geometry, data);
    de_mbr_resolve(walk->container.space, &walk->container.start, &walk->geometry, link);
    for (i = 0; i < 2; ++i) {
        earlier = &node->table.entries[i];
        if (earlier->range_valid &&
            (de_extent_contains(&walk->container, &earlier->extent, &inside) || !inside))
            earlier->issues |= DE_MBR_RANGE;
        node->table.issues |= earlier->issues;
    }
    if (node->table.issues & DE_MBR_RANGE) { stop(walk, node->table.issues); return DE_OK; }
    for (i = 0; i < walk->count; ++i) {
        earlier = &walk->nodes[i].table.entries[0];
        if ((data->range_valid && includes_lba(&data->extent, &walk->nodes[i].lba)) ||
            (earlier->range_valid && includes_lba(&earlier->extent, lba)))
            node->table.issues |= DE_MBR_METADATA;
        if (i + 1 < walk->count && data->range_valid && earlier->range_valid &&
            !de_extent_overlap(&data->extent, &earlier->extent, &overlap) && overlap)
            node->table.issues |= DE_MBR_OVERLAP;
    }
    walk->issues |= node->table.issues;
    if (!link->active) { walk->needs_block = 0; walk->complete = 1; return DE_OK; }
    for (i = 0; i < walk->count; ++i)
        if (!de_u64_compare(&link->extent.start, &walk->nodes[i].lba)) {
            stop(walk, DE_MBR_CYCLE); return DE_OK;
        }
    if (walk->count == walk->limit) { stop(walk, DE_MBR_BUDGET); return DE_OK; }
    walk->pending = link->extent.start;
    return DE_OK;
}

int de_ebr_unavailable(de_ebr_walk *walk)
{
    if (!walk || !walk->needs_block) return DE_INVALID;
    stop(walk, DE_MBR_UNAVAILABLE);
    return DE_OK;
}
