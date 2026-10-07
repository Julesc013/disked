# Captured-map slice findings

The first native corpus run found incorrect GPT omitted counts. Chained method
calls moved the entry array while another argument still read its size; C++14
does not sequence those evaluations as intended. The code now computes omitted
counts before moving either GPT entries or EBR nodes. The existing zero-omission
expectation was retained, and larger omitted-detail cases cover both paths.

Review also corrected the new empty-image test before the next run: zero declared
blocks have no LBA zero, so the established C90 reader returns DE_BOUNDS and no
parsed MBR. Empty captured bytes within a nonempty declared space instead report
truncation. DE-102 now spells out that distinction; no reader behavior changed.

Undecoded MBR/EBR records retain the actual available raw bytes without invented
decoded fields. Truncated/unsigned GPT headers omit uninterpreted fields instead
of presenting zero-filled workspace as observed metadata. The tests cover these
relationships, invalid UTF-16 bytes, embedded terminal/bidi text, and report data
remaining valid after the probe destroys its original input buffer.

The maximum workload checks all four 128-visit EBR budgets and both 128-active-entry
GPT arrays while retaining only eight detail rows per source. Explicit omitted
counts and aggregated findings remain present; the serialized report stays within
48 KiB. This is an in-memory interpretation test, not source capture, filesystem
mounting, UI parity or image-provider admission.

Final review found another presentation distinction: when the header's array
shape is invalid, its derived byte/block sizes were never calculated. Those
fields are now null rather than zero. The raw advertised count/width and issue
mask remain available, and a new native case checks the independent valid backup.
The initial full 38-group run used 70 integration cases; the final focused and
clean runs use 71. C90 reader code and the earlier expectations are unchanged.
