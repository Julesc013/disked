---
type: DiskEd Specification
title: Other hosts and storage domains
description: Preserve the universal direction without making distant ports release blockers.
resource: disked://spec/de-052
tags:
- disked
- platforms
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-052
  profile: disked-spec/1
  version: 0.1.0
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-031
  - DE-033
  - DE-050
  requirements:
  - DE-REQ-052-01
  - DE-REQ-052-02
---

# Other hosts and storage domains

## Host profiles

Plan Linux GTK3 and Qt6 profiles, BSD/Unix native CLI/TUI, macOS 10.6 AppKit x86-64, modern macOS AppKit/SwiftUI, classic Mac 7.6 m68k and 9.2 PPC. Each has a toolchain/runtime/ABI and frontend contract. Linux compatibility needs an exact libc/sysroot and toolkit build; "Qt6" alone is not an Ubuntu release guarantee. Classic Mac has resource forks and no assumed Unix shell; packaging must preserve its executable metadata. Modern macOS app bundles are platform-native directory structures, not a packaging failure.

Do not create placeholder GUI binaries to satisfy a matrix. A platform with no eligible GUI must declare an exception or remain a CLI/TUI development profile until one exists. The release catalog distinguishes a native-capable host with a missing implementation from a host that lacks desktop semantics. CPU breadth remains an extensibility target, not a falsely completed checkbox.

## Media programs

Tape/LTFS, optical CD/DVD/BD and session formats, floppy sectors/flux, disk images, RAID/pools, encrypted layers, object storage and distributed fabrics are separate capability programs. Candidate upstream tooling is reviewed for exact role and version. Mounting a foreign filesystem, recovering files, repairing allocation metadata and moving a volume are different capabilities.

## Remote systems

Enterprise arrays, SAN, multipath and cluster storage require lease/fencing and concurrent-use semantics. A local volume lock cannot prove another host is quiescent. Future Redfish/Swordfish/NVMe management providers must use their native authority models, not extend a local raw-write API with a network address. A disconnected agent returns uncertainty if it cannot know whether a remote effect committed.

## Portable integration discipline

Use contracts and fixture vectors across systems, not binary interchangeability. Where required primitives are unavailable, offer inspection, image-based planning or an offline/remote workflow with explicit limits. Retain the same operation ID and capability explanation across hosts so users can understand why a plan is recognized but not executable locally.

## Normative requirements

### DE-REQ-052-01

Future host/media profiles MUST retain distinct semantics and qualification states rather than inherit block-write capability.

**Verification:** Inspect planned profile catalog and negative media-role tests.

### DE-REQ-052-02

Clustered/shared storage mutation MUST require appropriate coordination beyond local mount/lock state.

**Verification:** Shared-LUN fixture refuses absent cluster authority.

## Related specifications

- [DE-031](../storage/address-spaces.md)
- [DE-033](../storage/providers.md)
- [DE-050](windows-targets.md)
