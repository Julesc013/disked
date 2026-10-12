# Implementer review: global FAT allocation

The paged-cell decoder reuses the existing C90 exact-cell contract, with checked
source/table windows and copy selection. Comparison-set publication is atomic at
the cell level; missing suffixes do not become free entries. Incoming/color/path
workspace is bounded and graph traversal is linear, iterative and cycle-aware.
Coverage and detail omission are independent, and later scan failures preserve
tree completion. Unreferenced-allocation qualification has explicit ownership,
coverage/copy/overlap prerequisites and supplies no recoverability or authority.

Reviewed against the predeclared DE-W028 contract. Independent count/graph oracles,
ordinary-file preservation and recapture controls pass, with the full native and
tooling regression at 0e414ccd. The aggregate consistency flag additionally denies
unreferenced allocation candidates while tree and graph dimensions remain separate.
Default tree-only behavior remains unchanged.
No product FAT command, extraction, mutation, mount, physical provider or release
is admitted. This is one implementer review, not independent-person/owner acceptance.
Continue auxiliary metadata, namespace and actual worker/frontend contracts under
the original full programme; preserve the separate recovery/storage/release gates.
