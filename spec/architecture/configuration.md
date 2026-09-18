---
type: DiskEd Specification
title: Configuration, state roots and resource packs
description: Portable payloads remain immutable while state and evidence have explicit ownership.
resource: disked://spec/de-013
tags:
- disked
- architecture
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-013
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  requirements:
  - DE-REQ-013-01
  - DE-REQ-013-02
---

# Configuration, state roots and resource packs

## Root model

Separate payload, configuration, state, cache, case, evidence, journal, recovery and secret roots. The binary may execute from read-only USB, optical media or a network share. Portable does not imply writable state beside the executable. A user-selected home or explicit managed-portable marker can choose roots; absence of installation metadata is not authority to write to the launch directory.

Configuration is human-authored TOML once a qualified parser is selected; machine manifests remain JSON. Precedence narrows authority: compiled invariants, organization policy, system policy, user policy, case policy, session settings, command request. Lower layers cannot weaken a higher prohibition. An expert user can see a policy explanation without acquiring implicit bypass rights.

## Privileged interpretation

The planner records the effective configuration/policy digest. The broker accepts only plan-bound policy material through an authenticated channel, not arbitrary current-directory files or environment variables. Source files, DLL search paths, language packs and plugins are untrusted until separately admitted. Secrets belong to dedicated providers and redaction-aware references, never embedded ordinary JSON plans.

## Embedded resources

Compile command descriptors, schemas, help, default policies, manifests, icons and localization into a deterministic read-only resource pack for the reference executable. Resources have stable IDs and source hashes. External overrides are explicitly versioned, constrained and ignored in safe mode. Embedded checksums detect corruption; they do not authenticate an image against an attacker who can replace both code and checksum.

## Concurrency and migration

Writable roots need ownership, ACL or capability checks, locking, atomic replacement and crash behavior. Never migrate state silently if an older running process might consume it. Keep old journal readers longer than writers. A failed migration retains the original artifact and explicit recovery instructions. Secret deletion and cache cleanup must not masquerade as media sanitization.

## Normative requirements

### DE-REQ-013-01

DiskEd MUST support a read-only payload root and explicit writable state/evidence roots.

**Verification:** Launch fixture composition from a read-only directory and verify no adjacent writes.

### DE-REQ-013-02

The broker MUST ignore ambient user search paths and unbound configuration after plan review.

**Verification:** Alter a current-directory config and environment variable before apply; verify refusal or no effect.

## Related specifications

- [DE-010](system.md)
