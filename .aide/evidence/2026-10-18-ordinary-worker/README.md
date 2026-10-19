# Ordinary worker qualification remains open

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

The fresh-logon alternative is unqualified. Do not repeat unchanged token/ACL/API
variants. The next investigation must identify the actual restricted-process DLL
initialization boundary before selecting another recipe. No broad group or
shared-object permission change is admitted by these observations. All
original protected-record, outside-write denial, hard-cap exhaustion, descendant
restriction, abrupt-controller exit and owned cleanup criteria still apply.
The full current x64 product suite and representative compiler/store journey
remain pending regardless of any primitive or diagnostic result here.
