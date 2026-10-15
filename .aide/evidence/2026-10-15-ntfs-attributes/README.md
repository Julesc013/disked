# Supplied NTFS attributes and mappings

DE-W078 advances original NTFS inspection with post-fixup attribute-envelope and
mapping-pair cursors. The expected contract precedes evaluation and records the
primary-reader differences, explicit compatibility choices and remaining scope.
No upstream code or tools were imported into or executed as the implementation.

The first working four-group NTFS run passes 247 attribute, 632 mapping, 1,729
boot and 964 record cases. Three additional attribute-header/layout cases bring
the attribute suite to 250 and pass on the same native artifacts. Actual native
API sentinels, protected original/restored buffers, header/build-boundary and
strict GCC/Clang C90 checks pass. These working observations are not an exact
source or complete product qualification. Retained working inputs describe the
current 250-case fixture; the first log and its case file describe the earlier
247-case selection.

Pre-qualification review then reproduced two false-positive envelopes at
`ab33609d`: signed-negative sizes and VCNs were treated as large unsigned values.
The correction retains raw bits and adds size/VCN diagnostics. Its 259-case
attribute suite and the two focused reproductions pass on the corrected working
artifact. `signed-correction/` retains baseline/correction observations and the
source inputs; no exact qualification is inferred from these working checks.

The finite recipe selects fourteen portable groups, one NTFS header, attributes
probe imports/security, strict syntax for all four C90 sources, and the complete
structural/context/spec-tooling floor:

```text
python .aide/evidence/2026-10-15-ntfs-attributes/reproduce.py --root PATH_TO_CHECKOUT --output NEW_OUTPUT_DIRECTORY
```

Names/values remain bounded raw observations; terminated lists are not complete
streams or namespaces. Compression/encryption, attribute-list joining, payloads,
held-source/provider/frontend, original targets/storage, owner and writer/recovery
or release qualification remain open. Earlier W075/report failures are retained
and are not cleared by this independent primitive.
