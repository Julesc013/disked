---
type: DiskEd Specification
title: Windows target profiles and qualification
description: NT-first builds with explicit loader, runtime, frontend and security limits.
resource: disked://spec/de-050
tags:
- disked
- platforms
generated:
  by: chatgpt/gpt-6-astra-pro
  at: '2026-09-17T12:00:00Z'
status: draft
disked:
  id: DE-050
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-012
  - DE-020
  requirements:
  - DE-REQ-050-01
  - DE-REQ-050-02
  - DE-REQ-050-03
sources:
- id: winui-deployment
  resource: ../references/sources.json#winui-deployment
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
---

# Windows target profiles and qualification

## Initial priorities

Windows XP SP3 x86, Windows 7 SP1 x64, Windows 10 x64 and Windows 11 x64 are required initial design lanes. Build the same fake-provider interaction slice on XP and a current NT host early, so modern imports or language/runtime assumptions are discovered before the core grows. ARM64 is a separate native target. Windows 10/11 marketing names are not sufficient profile identifiers: record minimum build, architecture, ABI, SDK, imports, CRT, GUI adapter and included providers.

One product release tag publishes multiple target assets. Do not create permanent OS-specific source branches or assume that a build for every major.minor version is useful. An old compatible binary can run on newer Windows with capability probing; a newer binary need not run backwards. Interchangeable means compatible semantics and formats, not identical machine code across CPU architectures.

## UI compositions

Reference: native Win32 Unicode GUI, CLI/TUI and built-in providers in a native executable. XP and 7 expose host-appropriate controls and API fallbacks. WinForms 4.0/4.8/4.8.1 and WinUI/.NET compositions remain alternate planned profiles. Their runtime, OS and CPU floors must be verified before publication, not inherited from an earlier conversation. An absent .NET Framework runtime means a managed GUI is not self-contained.

WinUI can have a single distributable extractive composition; that differs from a zero-extraction native image.[^winui] Record each property separately. A GUI dependency must not prevent a headless command from reporting why the GUI is unavailable. Test loader behavior before main, not only runtime branches.

## Other Windows lineages

NT4, Windows 2000, earlier NT, Win9x ANSI, Win16 and RT ARM32 are deliberate later profiles. Win9x raw-I/O is not NT raw-I/O. RT deployment and signing are a distinct gate; do not promise ordinary sideloaded desktop support. Modern ARM64 is not ARM32 Windows RT. A system with no modern ACL/IPC guarantees cannot silently inherit modern broker assurance.

## Publication rule

Record `planned`, `buildable`, `vm-qualified` and operation-specific hardware/recovery evidence separately. This archive lists target ambitions only. No Windows binary was built or run during specification generation. A profile cannot be advertised as supported until its exact artifact passes clean-VM launch, import audit, frontend parity and relevant provider tests.

[^winui]: Microsoft unpackaged WinUI deployment documentation; source registry `winui-deployment`.

## Artifact targets and host evidence

`catalog/targets.json` is the authored coverage/profile ledger. Planned research rows can retain unresolved fields; qualified artifacts require exact CPU, ABI, loader/import/static initialization, memory/address model, toolchain/runtime, provider closure and host records. One artifact may carry several exact host qualifications. The legacy ID `windows.nt11.x64.win32` remains unchanged and is not an NT 11.0 kernel claim. Do not silently rename public IDs or generate a Cartesian product of marketing releases and frameworks.

Win16 terminal behavior needs a separate piping/redirection/exit-status experiment: a rendered text window is not a proven CLI. XP x86 and XP x64, Win9x and NT, ARM32 RT and ARM64 Windows retain separate profiles. Server Core and recovery compositions declare absent desktop/installer facilities. Setup hosts and distribution channels have independent compatibility floors. Historical research never blocks a separately qualified current-Windows inspector.

## Normative requirements

### DE-REQ-050-01

Target profiles MUST distinguish architecture, loader/API floor, runtime, GUI and operation evidence.

**Verification:** Reject incomplete profiles and inspect exact release manifests.

### DE-REQ-050-02

OS-version assets MUST share semantic contracts without claiming cross-architecture binary interchangeability.

**Verification:** Compare schema/command IDs and run machine-specific launch tests.

### DE-REQ-050-03

All declared initial Windows lanes MUST be exercised before a Windows-wide support claim.

**Verification:** Qualification matrix has no untested entries marked supported.

## Related specifications

- [DE-012](../architecture/languages-and-build.md)
- [DE-020](../interaction/invocation.md)
