# NTFS directory-index inspection

The dev.65 composition adds `image inspect PATH --view ntfs-directory` to the
existing shared action. Supply explicit `--volume-offset` and `--volume-bytes`;
`--ntfs-version auto|3.0|3.1` defaults to automatic selection. Optional
`--directory-reference` is zero for discovered root FILE5, or a full reference
including its sequence. An ordinal alone is rejected before source access.
The [execution contract](../spec/catalog/ntfs-directory-command-prototype.json)
defines exact grammar, fixed maximum caps, projection, outcomes and native tests.

For a generated ordinary image whose selected volume begins at byte 173 and has
length 40960000, the invocation is:

```text
disked --json image inspect generated.img --view ntfs-directory --volume-offset 173 --volume-bytes 40960000
```

The owned reader and parent verification bind source metadata, window, profile,
reference, limits, epoch and actual exited process. Invalid controls fail before
source access. Well-shaped partial/refused/unresolved observations retain their
distinct results; no deadline releases source or request-slot ownership early.
Source reads and retained responses remain bounded by the existing collector.

Projection preserves original whole-file/capture and list hashes, exact total/
returned/omitted counts and acquisition flags. Entries retain original `name_hex`
and add escaped UTF16 code-unit `name_display`; display never normalizes source
names or executes terminal controls. A presentation prefix does not change capture
completeness. The response frame, including LF, is at most 524288 bytes.

The working corpus passes 100 checks through actual CLI JSON/human, JSON/NDJSON,
GUI/TUI/shell and independent worker/port comparisons. It covers both versions,
full references, exact 128-block graph, actual reads above 4GiB, complete unchanged
source hashes, an 82KiB display, nested projection limits, exact frame boundary,
invalid controls, lifecycle faults and late results. Exact clean source `6efc9a5b` passes all 163 x64 native groups, 63 C++
headers, C90/import checks and 247 tooling tests (two skips). Eight private
Win32 reader/worker groups and six headers pass; the new Win32 frontend is
unqualified. [Review and exact evidence](../.aide/evidence/2026-10-16-ntfs-directory-command/REVIEW.md). Two GUI fixture API/response-shape failures remain in
[working evidence](../.aide/evidence/2026-10-16-ntfs-directory-command/working/).

This is one bounded directory index, with namespace/collation/target-membership/
cluster-allocation verification explicitly false. Complete namespace/tree, lookup,
content, physical storage, further hosts and the full original 0.1.0 remain required.
Owner, licensing, production recovery/storage and release gates remain separate.
