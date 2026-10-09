# DE-W060 read-only native source consumer

Clean DiskEd source `23079a5a0d7c18d30706491b5862f9c675724e24` built and
executed a private C11 probe of exact Universal Setup CoreStatic source
`2e64f654b370f500ddbab45ae097df63352c3c25` on the selected unprivileged
Windows x64 host. The DiskEd-owned exporter and CMake project verified 84
upstream inputs; 26 local code/schema/license inputs were checked against Git.
No upstream scripts or build files were executed.

[Results](reproduction-23079a5/results.json),
[commands](reproduction-23079a5/commands.json) and
[review](REVIEW.md) distinguish a source consumer from an installed SDK,
CoreShared or live lifecycle qualification. The campaign ran 33 native
executions and 223 assertions. All 30 package/export tests passed; 215 tooling
tests ran, with 213 passing and two skipped. Structural validation passed
1,037 checks; the complete 293,509-byte context pack verified.

The retained probe is 1,548,800 bytes with SHA-256
`40d5bc1c5805c4ba106870ffc8d56d57d5dbd71cf34c0e1e5e4c3ab5bb84c08b`.
It is private fixture tooling, separate from the shipped dev.36 DiskEd
executable. Local artifacts and exact identities are in
`reproduction-23079a5/retained-artifacts.json`. Build flags, compiler metadata,
PE headers, direct imports and library symbols are retained separately.

The generic package verifier refuses DiskEd because this pin requires FacMan
metadata. Archive inspection establishes structure and source identity; a
payload-corrupt fixture passes inspection and fails independent content
verification. These are retained limitations, not successful package or
lifecycle qualification. The complete work unit, owner acceptance and full
0.1.0 programme remain open.

Reproduce with explicit local inputs and a new owned output directory:

```text
python .aide/evidence/2026-10-10-setup-source-consumer/reproduce.py --repository DISKED_REPOSITORY --source-revision 23079a5a0d7c18d30706491b5862f9c675724e24 --upstream-repository SETUP_REPOSITORY --package QUALIFIED_PACKAGE --inventory ORIGINAL_INDEPENDENT_INVENTORY.json --package-evidence PRIOR_PACKAGE_RESULTS.json --output NEW_REPRODUCTION_ROOT
```

The recipe requires the original `e1683b1` package-fixture qualification and
its independently retained inventory. It does not fetch a floating dependency,
install software, invoke Setup apply, alter another repository or publish.
The consumer artifact identifies one actual build; rebuilds are not claimed
to be byte deterministic.
