# Implementer review: bounded FAT volume capture

Reviewed the cell-request/decode delegation, shared region contract, runtime tree/
extent interpretation and ordinary-file adapter against the predeclared profile.
The shared callback alias preserves existing partition capture meaning; dependencies
remain narrow and explicit. Requests and outputs have checked windows/budgets,
selected FAT copies and owned lifetimes. Original names, physical slot offsets,
partial/damaged/cyclic/cross-linked outcomes and file slack remain distinct.

The library's selected-tree result cannot qualify global allocation, namespace,
content extraction or filesystem health. File/parent generation and repeated
region agreement remain narrower than an atomic snapshot or media safety. File
access is read-only; test controls have separate compiled targets and the normal
build ignores them. No native FAT product command or writer is admitted.

149 independent cases, protected cells, prior FAT regressions, all 91 native groups,
10 headers and tooling pass at exact source f98712a4. GCC 15.2 is syntax-only.
Every exercised read-failure boundary preserves established chain dimensions.
This is one implementer review, not independent-person or owner acceptance.
Continue global allocation/namespace and worker/frontend qualification under the
full programme; keep extraction/host/storage/journal/release gates separate.
