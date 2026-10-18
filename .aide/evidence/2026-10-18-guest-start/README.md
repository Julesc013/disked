# Guest bootstrap checkpoint

Base: `0e2e913381db71318e9ff27a27b3ba11dbd2e1a0`; product work remains DE-W105.

The final owner instruction selects Agents for routine automation and retains
Codex as an emergency administrator spare, with its existing SID and profile.
Both accounts are enabled and have non-expiring passwords. Codex received the
owner-supplied password through a SecureString; its account was not used for work
after being designated a spare. Guest Jules was not used or changed. The primary
credential remains encrypted outside Git, under the authorized host user.

`account-configuration.json` records the actual final settings. A first attempt
rejected an overlong account description; `account-configuration-first.json`
retains that failure. Shortening the description resolved it. Account/profile
deletion was never performed; the final instruction supersedes the earlier
request to remove Codex. The helper accepts only Agents and never automatically
falls back to the spare.

The guest's actual EnableLUA was initially 1 despite the earlier notification
slider change. An authorized guest-only bootstrap configured 0. The owner then
authorized a restart despite unknown concurrent work. `restart-result.json`
records a normal shutdown/start with its checkpoint preserved and host UAC
unchanged at 1. Subsequent Agents sessions verified guest EnableLUA=0 and an
administrator token. Guest CPUs remain four; dynamic RAM remains 1–16 GiB with
2 GiB startup. Final observed assigned RAM was about 2 GiB.

Early transport attempts failed, including directly after restart. After the
owner completed first-login setup, fresh Agents sessions passed account
inspection, final configuration, tool inventory and compiler-file inspection.
These observations establish a usable setup path, not uninterrupted availability
or product qualification. Earlier failures remain in `result.json` and separate
receipts. The guest PowerShell Direct service was restarted once during initial
bootstrap; no SSH/listener, host policy change or new software installation was
made. The owner explicitly returned guest-console control before final setup.

The compiler already exists at `C:\BuildTools`: toolset 14.44.35207 and compiler
file version 19.44.35228.0 match the project pin. SDK 10.0.19041.0, CMake 3.31.12
and Git 2.53.0.windows.3 are present. The Python launcher reports no installed
runtimes; the WindowsApps entry is an alias. No compiler invocation, native build
or product test ran in this checkpoint. Prepare a bounded guest Python runtime
and prove guest capacity/confinement/cleanup before native qualification.

The final `tooling-checks.json` retains 100 host coordinator tests: 99 passed,
one expected skip. Observed runner peak was 88,183 bytes; its workspace was
removed. `connection-checks-first.json` preserves an earlier mocked-test failure
caused by a cleanup flag's script scope. The correction retained the cleanup
assertion. Mocked checks do not establish guest or product qualification.
All 420 specification manifest entries were verified unchanged.

`finish-start.ps1` and its startup/refusal receipts are historical: the earlier
startup monitor missed its heartbeat deadline after one start and zero logins.
Its old two-CPU/3-GiB admission guard is superseded by the owner's configuration;
do not rerun it. The passwordless-Codex option in historical `inspect-guest.ps1`
is also obsolete; the final invocation used saved Agents credentials.
`source-transfer-plan.json` binds its original base; no checkout/archive was
created. `bootstrap-access.ps1` was copied earlier, but the successful initial
account creation used native Windows commands. `prepare-agents.ps1` was a copied
console proposal whose execution was not verified; final settings were applied
by `configure-accounts.ps1` through an authenticated Agents session.

Both copied guest bootstrap scripts were removed after content-hash checks:
6,115 bytes reclaimed, no other processes killed. Temporary console screenshots
were removed. Host `.aide-local` is empty; the reviewed cleanup receipt records
its earlier 199,470-byte removal. No build trees, test images or archives were
created. The shared viewer is left open and the checkpoint chain preserved.
`final-host-observations.json` records the existing backing file and free space;
VM boot/profile activity consumes real storage. No compaction was attempted.

The goal remains active. Next is the guest Python/runtime and hard-cap proof,
then bounded DE-W105 native qualification using the existing compiler. The old
host proof does not qualify the guest. Main promotion, owner acceptance and
release/full-0.1.0 completion remain separate and unclaimed.
