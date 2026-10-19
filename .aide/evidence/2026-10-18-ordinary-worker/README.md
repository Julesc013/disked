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

All completed runs above have separate account/profile/image/source cleanup
receipts. Volume/file identities in newer receipts use decimal strings to avoid
PowerShell JSON integer rounding; older rounded observations are not exact IDs.

The fresh-logon alternative is unqualified. Do not repeat unchanged token/ACL/API
variants. The next investigation must identify the actual restricted-process DLL
initialization boundary before selecting another recipe. No broad group or
shared-object permission change is admitted by these observations. All
original protected-record, outside-write denial, hard-cap exhaustion, descendant
restriction, abrupt-controller exit and owned cleanup criteria still apply.
The full current x64 product suite and representative compiler/store journey
remain pending regardless of any primitive or diagnostic result here.
