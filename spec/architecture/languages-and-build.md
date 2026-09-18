---
type: DiskEd Specification
title: Language, ABI and build policy
description: Small portable C strata with target-qualified native implementations behind stable contracts.
resource: disked://spec/de-012
tags:
- disked
- architecture
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-012
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-010
  - DE-011
  requirements:
  - DE-REQ-012-01
  - DE-REQ-012-02
---

# Language, ABI and build policy

## Working default, not premature lock-in

Use a small C90-compatible microcore for checked ranges, byte order, buffers and selected MBR/EBR/GPT primitives needed by DOS and early NT. Define exact-width types per target and assert widths; C90 does not provide `stdint.h`. On modern targets use native C++ behind a C boundary; select the exact language baseline only after the XP/7 toolchain spike. Rust is an eligible isolated parser/provider implementation where the target and dependency closure are qualified. Do not fork the semantic meaning to accommodate a compiler.

The first artifact is a native Win32 composition. C#, WinForms and WinUI remain optional GUI adapters, not planner or broker dependencies. OS/2, classic Mac and JC-DOS have native toolchain lanes. Python tooling runs on a modern development coordinator, not on every deployment target. A DOS product does not imply Python must run on DOS.

## Public C ABI

Use opaque handles, fixed calling conventions, explicit ownership, allocation callbacks where needed, versioned structures with `struct_size`, status codes and caller-owned buffers. Do not expose STL, exceptions, COM implementation types, toolkit objects or mismatched allocator ownership across the ABI. Structured errors carry stable codes and optional platform details. Cancellation callbacks cannot reenter mutable core state without a documented rule.

Negotiate protocol and schema versions separately from product version. Unknown critical fields and required features fail closed in mutation protocols. Extensible read-only descriptions can retain unknown fields. Preserve raw unknown fields when reserializing signed or hashed objects; do not normalize away information before verifying the source representation.

## Build authority

One target descriptor supplies compiler, SDK/sysroot, import policy, GUI choice, provider closure, CRT strategy and security flags. The build coordinator invokes CMake, MSBuild, Xcode, Watcom or a period toolchain as appropriate. It must not assume every historical compiler supports modern CMake. Store exact reproducibility limitations and redistribution restrictions for old SDKs.

Run import-table and minimum-CPU audits on outputs, not just source checks. Dynamic API probing prevents a modern optional import from raising the loader floor before startup. Build optimizations must preserve range checks and undefined-behavior protections. Static runtime linkage creates update obligations; it is not zero-dependency security.

## Normative requirements

### DE-REQ-012-01

Public native interfaces MUST have explicit ownership, versioning and calling convention, without language- or toolkit-private types.

**Verification:** Compile ABI examples with independent C and C++ clients.

### DE-REQ-012-02

Every target MUST have an exact toolchain/runtime/import declaration and a real launch test before a compatibility claim.

**Verification:** Inspect PE imports and run a clean target VM; do not count successful compilation alone.

## Related specifications

- [DE-010](system.md)
- [DE-011](repository.md)
