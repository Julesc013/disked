# DE-W056 partial metadata preparation

At base 80b51ed6 with working-tree changes, 631 cases/10 methods pass explicit
name/time/attribute mapping and actual Windows CP437/CP850 conversion. Every
byte of both native pages matches Python's independent codecs. Twelve actual
ordinary-file cases/five methods retain 980 metadata frames: 300-entry FAT12/
16/32 trees, deep parents, cross-page/sector long names, invalid original UTF16,
explicit synthetic mapping, latest-page membership, cancellation and source
fault refusal. Exact original records/slots and source hashes stay unchanged.
Preparation creates no output. Candidates do not claim native application.

All six selected native groups pass, including the existing content, held-file
worker and frontend regressions. The final tooling suite runs 238 tests: 236
pass and two skip. Structure, manifest, context, source map and dependencies
pass; 242 current source files have one owner-map entry each. Two new standalone
headers and the modified held-file header compile in the Windows development
lane. The two native code pages are explicitly selected; no host-default,
best-fit, replacement or Unicode normalization fallback is used.

These are dirty development results, not a clean frozen full native campaign.
This completes a necessary preparation component, not the recursive backend.
Immutable effect/resource definitions and grants, create-only destinations,
ordered durable original metadata evidence, actual native application/readback,
contained writer lifetime/interruption and complete exact-source qualification
remain. No owner, production, physical-media, other-host or full 0.1.0 acceptance
is claimed. DE-W056 stays active; keep this partial checkpoint on dev.
