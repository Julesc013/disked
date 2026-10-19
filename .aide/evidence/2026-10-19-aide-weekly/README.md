# AIDE source/schema review — 19 October 2026

Selected dev revision: `7877e05655ee33fa99583afe4855fac6a4910292`.
Tree: `e6352e12de2f04cb8ef2e203e4325ee08fa476f1`.
Prior pin: `6f2abc4cd69e0d94f86a00495cb8feeebe20398a`.

Complete tree identity comparison covers 16,824 current entries. There are 2,773
changed tree entries, including 2,592 blob paths; this is not a semantic review
of every changed implementation. No entries under `.aide/protocol/` or the OKF
decision pages changed. README status, limits, authority and licensing sections,
the exact queue schema and release metadata were inspected. Three selected Git
blobs are independently checked against their Git blob identities and SHA-256.
No upstream checkout, clone, installer, worker or runtime was executed.

`selected-source.json.xz` contains those source bytes and the release observation.
`source-review.json` records its compressed and uncompressed hashes, sizes and
comparison scope. The archive is 11,908 bytes and round-trip verified. Source
acquisition used a managed workspace which was removed afterward.

The first tree endpoint accepted a commit alias and echoed that alias in its
`sha` field. That preliminary observation is retained and is **not** the admitted
tree identity. The corrected fetch resolves `git/commits` to the exact tree,
requests the tree by that identity and verifies both before adoption.

`validation.json` records all 98 actual WorkUnit exports against the unchanged
upstream schema, with exact exported hashes and nonzero complete ID-set checks.
Every record remains planned/NOT_RUN/validated=false and
authorizes_implementation=false. Fresh 17 affected bundle/export tests,
1,325 structural checks, generated index and manifest checks pass. The earlier
full 253-test/two-skip run and fixture follow-up checks remain separately scoped
under `../2026-10-19-managed-fixtures/`; no latest full native pass is implied.

The release API and current README agree that Lite1.1.0 is published. They declare
a T3 local Windows10 19045/Python3.14.8 CLI profile. Publication checkpoint9cead252
and payload source447e393b are distinct identities. These are upstream claims;
no release asset was downloaded or independently verified, and no live DiskEd
consumer was installed/imported/qualified. Previous pin/release observations
remain in history. Next source review target: 26 October.

The full DiskEd0.1.0 goal and DE-W105 remain active. Current native qualification
still awaits the ordinary confined worker and complete current x64 campaign.
