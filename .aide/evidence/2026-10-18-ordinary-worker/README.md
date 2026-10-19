# Ordinary worker qualification remains open

Current result: the original 32 MiB controls, representative restricted x64
compiler/production-store journey and complete 512 MiB controls pass. See
`thirtieth-full32-pass.json`, `thirty-third-native-store-pass.json` and
`thirty-fourth-full512-pass.json`, with their separate cleanup receipts. The
full current product suite remains pending. Earlier failures below are history.

This is a guest-only development experiment under the existing owner grant.
Agents coordinates. Each run creates one nonce/SID-bound **temporary standard
user**, a new fixed 32 MiB virtual disk inside the guest and private UI objects.
No customer/physical media, shared-account resets, extra persistent administrator,
host UAC change, profile loading or product-record ACL relaxation is involved.

The original candidate uses only its exact user SID as a write-restricting SID.
That token currently creates processes which exit `0xC0000142` before Python
executes. These are environment/launcher failures, not native product passes.

Retained attempts distinguish actual process startup from API success and from
diagnostic collection completeness:

- `first-description-refusal`: description exceeded Windows' 48-character bound;
  no actor/image creation. The preimage cleanup is independently recorded.
- `second-handle-list-refusal`, `third-launch-diagnostic`: extended WithToken
  startup is rejected; invalid basic standard handles give a different error.
- `fourth-basic-startup-diagnostic`, `fifth-private-ui-refusal`: basic launch
  creates processes, but full rights and medium labels on private UI do not
  resolve DLL initialization failure.
- `sixth-startup-partial`: the fresh unrestricted standard-user control starts
  and initializes USER32. Later cases hit a harness log-name collision. Its raw
  `pass` denotes diagnostic collection, and does **not** establish complete
  execution of the declared variants; the collision is corrected afterward.
- `seventh-default-dacl-diagnostic`: distinct logs allow all declared calls.
  The standard control starts; restricted startup still fails. Changing only
  the private token's default ACL does not fix it.
- `eighth-own-token-diagnostic`: a trusted fresh-user bootstrap derives its own
  restricted token and successfully creates a job-inherited AsUser child; that
  child also exits `0xC0000142`. Changing the launch API did not resolve startup.
- `ninth-fresh-logon-diagnostic`: adding only the actual fresh logon SID alongside
  the fresh user SID also fails before Python entry. The ordinary standard-user
  control still starts, and all owned resources retire.
- `tenth-minimal-loader`: the standard pure-Python observer reaches every import
  and DLL marker; the restricted process produces no breadcrumb. Its collector
  also exposes a CRLF/LF mismatch. Raw evidence is retained.
- `eleventh-actor-ui-diagnostic`: explicit LF output fixes that collector issue.
  Standard reaches all markers; restricted still exits `0xC0000142` without a
  breadcrumb. A trusted actor bootstrap reports access denied during private-UI
  setup, before it creates its restricted child. Exact failing setup API is not
  yet identified. Diagnostic collection passes; worker admission remains false.

All completed runs above have separate account/profile/image/source cleanup
receipts. Volume/file identities in newer receipts use decimal strings to avoid
PowerShell JSON integer rounding; older rounded observations are not exact IDs.

Earlier "before Python" shorthand was an inference from the original observer's
missing receipt, which followed imports. The minimal observer narrows the fact:
the restricted process produces no first breadcrumb. Later exact-image loader
observations identify the failing module and distinguish successive failures:

- Attempts 12/15 identify KernelBase initialization failure for user-only and
  fresh-user plus Restricted Code SID tokens. Attempt 13 records object-directory
  access differences, but does not establish that those caused the failure.
- Attempts 16/17 show successful watched DLL/shared-section opens and mappings.
  Neither watched port-connect function occurs; this is a limited observation.
- Attempts 18-20 expose collector bounds/thread/stop defects. These are failed
  diagnostic collections, with the restricted case unrun. Partial traces are
  preserved where available; all owned cleanup completed. Attempt 21 corrects
  collection and records subsystem-client success in both token cases.
- Attempt 22 binds read-only binary analysis to the exact guest KernelBase hash:
  the baseline returns true at initialization stage 700; restricted returns
  false at stage 600. These private offsets are not a Windows API or DiskEd ABI.
- Attempt 23 compares both launch modes in one run. Explicit detached launch
  passes KernelBase stage 700 but then fails **bcrypt.dll** initialization before
  Python entry. The original no-window case still fails KernelBase at stage 600.
  Detached launch therefore resolves one observed obstacle, not worker startup.

The current finite probe captures native file/registry arguments and statuses
for the detached failure. The prior three-case control remains retained; this
new single-case probe does not claim a new baseline. No shared-object ACL,
product-record ACL, privilege or storage-budget expansion is authorized by
these results. All completed native experiments have owned cleanup receipts.

Attempts 24/25 identify a concrete crypto-device denial: `NtOpenFile` requests
`0x100003` on `\Device\KsecDD` and returns `0xC0000022`. The ordinary bootstrap
queries the existing DACL with READ_CONTROL only. The RC ACE grants `0x1200a9`,
which lacks FILE_WRITE_DATA (`0x2`); the fresh user has no device-specific ACE.
No selected device-control call occurs before the failure. This observation
explains why the two-SID write restriction is incompatible with this startup
path. It does not qualify another token or authorize broad write-granting SIDs.

The next execution recipe must retain the hard filesystem boundary and all
original protected-record, outside-write, descendant and interruption controls.
Any proposed guest setup exception needs explicit scope, agent review and
verified retirement before admission. No crypto-device ACL was changed in
attempts 1–25.

The fresh-logon alternative is unqualified. Do not repeat unchanged token/ACL/API
variants. Use the now-observed console and crypto-device boundaries when
selecting another recipe. No broad group or shared-object permission change is
admitted by these observations. All
original protected-record, outside-write denial, hard-cap exhaustion, descendant
restriction, abrupt-controller exit and owned cleanup criteria still apply.
The full current x64 product suite and representative compiler/store journey
remain pending regardless of any primitive or diagnostic result here.

Attempts 26–29 prove the narrowly scoped guest setup: a journaled ACE gives only
the fresh actor SID the observed `0x100003` KsecDD access. Actual helper interruption
and recovery, exact removal, and failure of a new restricted process after removal
are recorded. The ordinary worker retains exactly fresh-user and Restricted Code
restricting SIDs, medium integrity and no administrator/AppContainer identity.
No filesystem/product-record ACL or host setting is relaxed. A fresh containing
job is required for each command; every owned member retires before removal.

Attempt 30 passes all original 32 MiB controls. Attempts 31–32 compile real
production helpers but expose prefixed kernel-object path failures; the first
cleanup refuses nested source entries, then exact-source-parent cleanup succeeds.
Attempt 33 uses the default namespace, verifies the ordinary session-zero alias
identity and passes actual protected user-only record and lease reopening. Its
x64 executable has only ADVAPI32/KERNEL32 direct dependencies.
Its actual artifact hash/length are in the receipt; no executable is retained.

Attempt 34 passes every primitive control at 512 MiB. It writes 518,717,440 bytes
before disk-full 112, observes zero filesystem free bytes, removes the fixture
and restores the prior free capacity. Normal and interrupted worker trees,
temporary ACE, actor/profile, image and source copies retire. This qualifies the
declared guest execution primitive, not the full native product or other hosts.
