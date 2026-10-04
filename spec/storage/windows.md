---
type: DiskEd Specification
title: Windows NT provider strategy
description: Windows-native depth without treating storage restrictions as bypass targets.
resource: disked://spec/de-034
tags:
- disked
- storage
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-034
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-033
  - DE-032
  requirements:
  - DE-REQ-034-01
  - DE-REQ-034-02
sources:
- id: windows-shrink
  resource: ../references/sources.json#windows-shrink
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
---

# Windows NT provider strategy

## Discovery first

Use documented Win32 handles, storage-property queries, volume APIs and disk-layout IOCTLs, with runtime capabilities determined per exact OS/API/provider. Modern Storage Management can enrich topology but must not become an XP-wide assumption. VDS is a separate optional legacy provider. Record native and independently decoded metadata without flattening partitions, volumes, disks, VHDs, pools and encryption into one object.

## Operation selection

Prefer a qualified native online operation. Otherwise offer a qualified Windows-hosted external provider, a native offline recovery operation, a foreign recovery provider, or image-first workflow. An unsafe active-volume move remains offline; it is not solved by administrator elevation or a new driver. Non-system drive letters do not prove quiescence: page files, open handles, filter drivers and remote users still matter.

Partition layout IOCTLs update metadata, not filesystem contents. Microsoft documents `FSCTL_SHRINK_VOLUME` from Vista with NTFS/RAW support and a multi-step allocation-handling workflow. The XP profile therefore cannot simply reuse that call.[^windows-shrink] The implementation must independently establish availability, filesystem state, lock semantics and postconditions for each API.

## Windows-specific layers

Prioritize NTFS/FAT/exFAT, mount-manager identity, VHD/VHDX, boot/BCD/ESP/MSR/WinRE and BitLocker-aware inspection. Later plans include Storage Spaces, LDM, ReFS and VSS coordination. Unlocking encryption, suspending protectors and moving encrypted content are distinct operations. Do not log keys or assume a volume copy repairs boot measurements. VSS snapshots are not general partition-table rollback.

## Legacy and hardened environments

An XP x86 profile uses period-compatible imports and tested native CRT behavior; a Windows 7 x64 build is a separate profile. Modern x64/ARM64 adds qualified security mechanisms. Missing OS security guarantees must be declared, not emulated with a process argument called `authenticated`. Windows RT ARM32 is an OEM/research lane pending its deployment/security review, not modern ARM64 Windows under another name.

Use no custom kernel driver in the initial plan. Driver need, lifecycle, signing, vulnerability response and qualification require a separate decision, justified by an essential capability that documented user-mode and offline paths cannot supply.

[^windows-shrink]: Microsoft FSCTL_SHRINK_VOLUME documentation, recorded in the source registry.

## Permission and consistency boundaries

Report native API availability separately from raw-access permission and fresh target eligibility. Standard-user image and saved-report work stays available when physical-device access is denied. VSS acquisition must follow [DE-036](acquisition-consistency.md), with participating writers/volumes and snapshot lifetime, rather than equating live raw reads with a coherent backup.

Server/Core/recovery, hypervisor attachments, event-log/ETW reporting, PowerShell and enterprise policy are separate qualified adapters. None is an initial loader dependency. Computer Management and shell entrypoints follow [native integration](../interaction/native-integration.md); they do not change the storage driver's capabilities.

## Normative requirements

### DE-REQ-034-01

Windows capabilities MUST be checked per API, filesystem and OS profile; XP MUST NOT inherit Vista-only shrink support.

**Verification:** API-availability fake fixtures and real XP import/launch qualification.

### DE-REQ-034-02

System/boot/encrypted or layered storage MUST be routed through dedicated providers and preconditions, not raw bypasses.

**Verification:** Reject unsupported BitLocker/Storage Spaces/system-volume scenarios.

## Related specifications

- [DE-033](providers.md)
- [DE-032](partition-tables.md)
