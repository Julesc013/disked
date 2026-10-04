---
type: DiskEd Specification
title: Distribution channels and servicing owners
description: Generate carriers from finalized payloads and assign one owner to each managed resource.
resource: disked://spec/de-065
tags:
- disked
- delivery
generated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
status: draft
disked:
  id: DE-065
  profile: disked-spec/1
  version: 0.1.1-proposed.2
  authority: proposed-normative
  review: pending
  risk: R2
  depends_on:
  - DE-060
  - DE-063
  requirements:
  - DE-REQ-065-01
  - DE-REQ-065-02
updated:
  by: codex
  at: '2026-10-03T17:24:09.000824+00:00'
  scope: 2026-10-04 supplied-proposal reconciliation; owner review pending
sources:
- id: review-inputs-2026-10-04
  resource: ../references/sources.json#review-inputs-2026-10-04
---

# Distribution channels and servicing owners

## Channel and owner matrix

| Carrier/channel | Resource owner |
|---|---|
| Direct EXE or portable ZIP | No installer owner until explicit enrollment. |
| Qualified Universal Setup installation | Universal Setup product binding. |
| MSI | Windows Installer. |
| MSIX/App Installer | Windows package deployment. |
| Store EXE/MSI | Submitted installer and its servicing model. |
| Store MSIX | Windows package deployment. |
| WinGet/enterprise distribution | Selected installer/package owner plus distribution policy. |
| OS/OEM component | Applicable OS servicing owner. |

One product definition supplies selected component closure, signed payload, preservation policy and channel projections. Carrier, channel, target, installation scope and servicing owner are separate. A manifest is not a channel approval. No self-updater or Universal Setup path independently overwrites MSI/MSIX-owned resources. A full nested installer in an MSI custom action is not the default reuse mechanism. Channel migration requires explicit ownership handoff or distinct nonconflicting roots.

## Release eligibility

Every channel qualifies its own host floor, features, signing, silent/offline behavior and update contract against dated primary documentation. Current [Store EXE/MSI requirements](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msi/app-package-requirements) include a fixed versioned HTTPS installer, signing, silent installation and a complete offline installer. That route is separate from MSIX eligibility. [MSIX tooling limitations](https://learn.microsoft.com/en-us/windows/msix/packaging-tool/tool-known-issues) include unsupported driver installation; a driver-dependent selection needs another qualified carrier. Refresh policy before submission rather than freezing a future policy date from supplied commentary.

Publish only built and qualified assets: portable payload/archive, optional Setup wrapper, symbols, notices, source, provider/integration/SDK/recovery packs where present. Derive filenames, checksums and download metadata from final staging. The public basename stays `disked` (Windows display casing may be `DiskEd.exe`; legacy `DISKED.EXE`); never ship case-only variants together. Native package eligibility does not change a legacy application's runtime floor.

## Normative requirements

### DE-REQ-065-01

Each installed resource MUST have one servicing owner; channel changes MUST preserve or explicitly transfer ownership and active recovery dependencies.

**Verification:** Attempt USK repair of MSI-owned payload, concurrent owner updates and channel migration; reject competing writes and preserve retained generations.

### DE-REQ-065-02

Channel releases MUST use exact finalized payloads and current channel-specific qualification; no generated carrier or signature alone establishes approval.

**Verification:** Check offline/silent/versioned Store fixture inputs, incompatible driver/MSIX selection, immutable payload equality and missing channel evidence.
