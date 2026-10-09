---
type: DiskEd Specification
title: Universal Setup boundary and installation modes
description: Setup owns software lifecycle; DiskEd owns storage operations.
resource: disked://spec/de-061
tags:
- disked
- delivery
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-061
  profile: disked-spec/1
  version: 0.1.4-proposed.1
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-060
  requirements:
  - DE-REQ-061-01
  - DE-REQ-061-02
sources:
- id: usk-policy
  resource: ../references/sources.json#usk-policy
- id: ulk-readme
  resource: ../references/sources.json#ulk-readme
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
- id: setup-fixture-source-2026-10-10
  resource: ../references/sources.json#setup-fixture-source-2026-10-10
- id: launcher-background-source-2026-10-10
  resource: ../references/sources.json#launcher-background-source-2026-10-10
- id: setup-source-consumer-2026-10-10
  resource: ../references/sources.json#setup-source-consumer-2026-10-10
updated:
  by: codex
  at: '2026-10-10T00:00:00Z'
  scope: DE-W060 read-only native source consumer and explicit generic verifier gap; owner review pending
---

# Universal Setup boundary and installation modes

## Separation

Universal Setup installs, verifies, repairs, moves and removes DiskEd's software payload. DiskEd interprets and transforms storage. Universal Launcher can discover and launch DiskEd but is not required to run it. Do not embed the full Setup engine into the DiskEd broker or maintain product-specific installer file lists that diverge from portable staging.

The preferred optional `setup` bundle contains the exact DiskEd portable payload plus its package contract. It can extract, manage a portable root, install per user or install system-wide where implemented. These are desired integration commands, not claims that the current upstream implements every mode. The observed Setup source contains restricted acceptance gates; DiskEd must honor the actual upstream contract rather than bypass them.

## Deployment scope

Unmanaged run-in-place writes no install record. Managed-portable uses an explicitly chosen root and owned state. Per-user installs only in authorized user scope. System-wide adds shared integration after elevation. The detailed strict/registered/native-package distinctions are owned by DE-063. Every mode keeps payload, configuration, evidence and recovery ownership distinct. Copying a portable binary does not authorize registry integration, PATH edits, services, file associations or network acquisition.

## Integration inputs

Supply product identity, target profile, signed payload tree, component/license closure, state-root policy, optional shortcuts and associations, upgrade/migration compatibility and uninstall retention. Setup returns its own plan, verification and lifecycle evidence. Storage journal/evidence remains DiskEd-owned. An update package must not import a new storage-provider authority without that provider's admission.

## Exact upstream work

A dedicated work unit pins Universal Setup and Launcher revisions, reads exported headers/schemas and maps the product package. It must test extraction equality, user/system scope, occupied-root refusal, rollback boundaries and preserved customer data. No blind dependency on sibling worktrees or hardcoded absolute paths is allowed. Host toolchain support is verified for each setup asset; an XP disked binary does not automatically imply modern Setup runs on XP.

## Embedded host and consumer boundary

Inactive H inside D is permitted by [DE-060](composition.md), without granting the storage broker software-lifecycle authority. Explicit setup inspection/maintenance follows the shared lifecycle interface and a separately authorized owner. The actual upstream consumer kit must be pinned and read before use; the supplied reports of SDK targets and later dev behavior are inherited leads, not current consumer qualification.

DiskEd owns product selection, storage semantics and active-operation dependency reports. Universal Setup owns generic software lifecycle as qualified; MSI/MSIX owners retain their resources. [Deployment profiles](deployment-profiles.md), [acquisition policy](component-acquisition.md) and [channels](channels-and-servicing.md) define DiskEd's requirements without forking upstream schemas. No other repository is changed by this task.

Maintenance distinguishes pause requested, checkpoint reached, resources released, recovery still dependent and unknown/unreachable. It cannot treat unreachable as quiescent. Retain exact generations or defer. Generic upstream gaps become consumer test requirements for DE-W060/062, not a private fallback installer.

## Initial fixture binding

The [fixture profile](../catalog/setup-fixture-prototype.json) selects exact
local Setup source `2e64f654b370f500ddbab45ae097df63352c3c25`; the
[source record](../references/sources.json#setup-fixture-source-2026-10-10) and
`external/universal-setup/source-lock.json` retain Git blobs,
byte counts and hashes. This is a local observation, not a claim about current
remote heads. Five unmodified MIT product/source/component/recipe/state-reference
schemas are retained for offline validation. Launcher source is independently
pinned as optional background; it is not a runtime dependency.

Setup's exported C ABI has four `usk_*_v1` functions and CMake SDK targets
Headers/CoreStatic/CoreShared. Product-package/recipe conformance remains
fixture-qualified and is not the callable command request. The inspected
source restricts managed-portable mutation behind a separate human live-lane
acceptance. DiskEd does not promote that gate or claim its own integration from
upstream retained tests. Source inspection is not a native SDK build or ABI test.

The DiskEd binding constructs an offline portable ZIP from a separately
enumerated nonempty inventory and maps exact entry paths, integer byte counts
and raw hexadecimal hashes into `usk.product_package.v1`. Recipe version/digest,
component set and topology must agree, beyond independent field types. Fixture
verification and extraction require separately selected original inventory and
native build-info; an internally consistent replaced package cannot redefine
the expected bytes. Schema references resolve only from the pinned local closure.

This provisional profile selects Windows x64 `0.1.0-dev.N` and an immutable
payload with external configuration/case/recovery/evidence roots. Those external
roots acquire no package ownership. Empty authenticity/license/SBOM references
mean no release qualification; source/launch evidence and owner licensing remain
separate. Recipe `verify` is an authored selection, not a live SDK invocation.
The minimum reader is a requirement; `maximum_tested_reader` is `not_run`.
The upstream schema allows this string, without proving a real consumer would
accept it or establishing installed-state compatibility.
Install/repair/update/move/uninstall, per-user/machine, embedded hosts and native
carriers remain unavailable through this binding.

Extraction writes ordinary files only below a new explicitly marker-owned
fixture child. Every existing root, including an empty root, refuses. A write
failure retains partial output with no cleanup, replay or rollback claim.
Generated occupied-root, foreign/case/evidence/recovery and interruption tests
must preserve exact bytes. This stricter fixture rule does not redefine
upstream empty-target policy. No installed-state truth, registration, upstream
script execution, real installation, elevation, signature or publication is
created. Quiescent fixture path checks are not hostile-filesystem isolation.

## Native read-only source consumer

The [source-consumer profile](../catalog/setup-source-consumer-prototype.json)
selects ABI 1.0, Windows x64/MSVC 19.44, static release CRT and a C11 consumer
of exact CoreStatic source. `external/universal-setup/native-source-lock.json`
binds 84 original source/header/schema/build/license inputs. A DiskEd-owned
exporter verifies all blobs before creating a new disposable root; a separate
DiskEd-owned CMake project verifies the bytes before compiling. Original core
and Zlib code is unmodified; upstream scripts and CMake are not executed.
Original MIT/Zlib notices accompany the export. This source consumer is not
an installed SDK, CoreShared or shipping DiskEd integration qualification.

Only policy/command discovery, local archive inspection, package verify/audit
and unconfigured read-only planning are admitted to the private probe. Other
commands refuse before context creation. Every request has finite byte/response
budgets, dry-run set, and null state, acceptance-root and activation pointers.
Copy borrowed response bytes before another call or context destruction.
Retain both C return/status and the supplier's JSON outcome: a zero probe exit
does not mean the requested supplier operation succeeded. Context allocator
balance does not claim that all internal provider memory uses that allocator.

At this pin, `package.verify` and `package.audit` require FacMan manifest and
component formats plus Factorio binding identity. The generic DiskEd package
fixture therefore refuses, despite conforming to product-package/recipe
schemas. This gap blocks generic callable verification; it does not authorize
disguised identity, copied installer lists or a private fallback lifecycle.
`install_local.plan` without lifecycle configuration refuses
`live_target_acceptance_required`; no valid plan or live authority is inferred.

The public archive inspector reports structural entries, stable source-read
identity and source hash. It does not prove payload CRC/decoded bytes,
authenticity, extraction or compatibility. Keep independent original-inventory
content verification mandatory. A content-corrupt structurally valid archive
can pass inspection while failing that verifier. Generated source, case,
evidence, recovery and foreign fixtures must remain byte exact after calls.

## Normative requirements

### DE-REQ-061-01

Setup MUST consume the authoritative portable payload and MUST NOT own or execute DiskEd storage transformations.

**Verification:** Integration boundary test and byte-equality verification.

### DE-REQ-061-02

Each lifecycle mode MUST be qualified against the pinned upstream implementation; planned modes MUST be reported as unavailable.

**Verification:** Exercise occupied-root, scope and unsupported-runtime refusals.

## Related specifications

- [DE-060](composition.md)
