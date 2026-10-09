---
type: DiskEd Specification
title: Artifact completeness and publication checks
description: Verify required content independently of archive integrity and distinguish historical audit claims.
resource: disked://spec/de-077
tags:
- disked
- development
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-077
  profile: disked-spec/1
  version: 0.1.2-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-004
  - DE-060
  - DE-074
  requirements:
  - DE-REQ-077-01
  - DE-REQ-077-02
updated:
  by: codex
  at: '2026-10-09T00:17:57.213441+00:00'
  scope: DE-W063 independent local staging inventory and bounded ZIP completeness checker
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Artifact completeness and publication checks

## Independent expected inventory

A matching checksum identifies bytes; a valid empty archive can still omit the entire product. The supplied audit reports such an earlier archive. That archive itself was not supplied to this task, so its size, contents and historical test counts remain attributed external claims, not newly reproduced results.

Before packaging, independently enumerate reviewed staging: required entrypoints, safe relative paths, regular-file types, byte sizes and content hashes. Refuse duplicate/case-colliding paths, traversal, absolute names and unapproved links. The final archive must match that nonempty expected inventory, not an inventory derived only from the archive being checked. Extract into disposable storage with containment checks and validate expected content before executing any explicitly approved entrypoint.

After an authorized publication, download and compare delivered bytes. Record staging identity, final archive and downloaded hashes, tool versions, actual commands and limitations. Keep completeness, integrity, authenticity, compatibility and runtime correctness separate. Local spec manifests enumerate source content; they are not signatures or proof that a separately packaged release contains it.

## Scope

Artifact-validator implementation and an empty-but-valid archive regression belong to the release-tooling work unit. The supplied claim of 15 archive-checker tests is not an executable checker in this repository. The native repository now contains its own checker and owned regression fixtures
below; the supplied historical count is not their evidence. Product runtime and platform checks apply to the actual composed artifact once one exists.

## Local checker implementation contract

`tools/release/artifact_check.py` implements the proposed
[artifact checker profile](../catalog/artifact-checker-prototype.json).
`inventory` reads quiescent reviewed local staging, requires a nonempty explicit
entrypoint selection, and enumerates sorted regular file paths, sizes and SHA-256
hashes before packaging. It rejects links, special files, empty directories and
unsafe/colliding paths. Output is created without clobbering outside staging.
The inventory still needs actual owner review; the tool cannot approve it.

`verify` reads that separate nonempty inventory and streams ZIP entries against
it. Single-volume stored/deflated ZIP supports bounded classic/ZIP64 metadata,
local headers and data descriptors. Unsupported carriers, encryption/compression
and non-ZIP64 extra fields refuse. Expected parent directory entries are optional;
unreviewed directories, missing/extra/duplicate/case-colliding files, unsafe names,
link/reparse/special entries and changed size/CRC/hash reject. Exact NFC names are
preserved; unsupported names refuse rather than silently normalize. Conservative
Unicode case folding also checks directory component spelling.

Central-directory and whole-source budgets are checked before ZIP metadata is
loaded. The complete raw compressed extent is decoded with bounded output buffers;
declared lengths cannot hide additional output. Require exact deflate EOF with no
compressed suffix, actual output size/CRC/hash, matching local ZIP64 sizes and
descriptor values, and contiguous nonoverlapping local records through the central
directory. File content is streamed in bounded reads. Limits for counts, JSON,
metadata, paths, content and archives are explicit in the profile; they are not
measured allocator/time guarantees. The verifier never extracts or executes
archive content. A pass identifies completeness and hashes only; authenticity,
publication, extraction and runtime remain `not_run`.

Staging checks compare path/descriptor identity, size and modification time, then
each API's own before/after fingerprint, and recheck files/directories after the
walk. Windows path and descriptor APIs may expose different legacy ctime values;
ctime is compared within the same API, without discarding identity/size/mtime
checks. Quiescent reviewed staging is required. These checks are not a hostile
concurrent-filesystem sandbox or atomic directory snapshot. Device/remote/alternate-
stream source namespaces refuse before opening. No platform/runtime claim follows
from successfully checking bytes; unsupported hosts/carriers remain unverified.

The owned suite includes valid-empty, omissions, extras, duplicates, collisions,
unsafe names, links, changed bytes, malformed/bounded metadata, CRC/deflate faults,
ZIP64/data-descriptor controls and no-clobber CLI behavior. Actual build staging
and exact source-bound results belong in DE-W063 evidence, separately from owner
acceptance and release publication.

## Normative requirements

### DE-REQ-077-01

Every distributed artifact MUST match an independently reviewed nonempty staging inventory with required entrypoints and safe unique paths.

**Verification:** Before release, test empty-but-valid, missing, extra, duplicate/case-colliding, traversal and changed-byte archives against the staging contract.

### DE-REQ-077-02

Publication evidence MUST distinguish local packaging checks, delivered-byte checks, authenticity and product qualification, and MUST report unexecuted checks as not run.

**Verification:** Review a release record with a missing download check or runtime evidence; no publication/runtime success may be inferred from checksum equality.
