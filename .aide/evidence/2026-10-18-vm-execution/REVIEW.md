# Shared guest execution preparation

Base: `b0a168549b4f9f4dfade0825281f81a3df475ff3`, branch `dev`.
Product work remains DE-W105; the full 0.1.0 scope and owner/release gates remain.

BLACKGLASS-WIN1 was incorrectly described as the test VM. Hardware inspection
identified the physical Gigabyte host. The existing Hyper-V `Windows 10` guest
is VM `3ebbe558-91b9-435b-96e4-0c8199bd38ad`, reporting BlackGlass-HyperV and
Windows 10 Enterprise 19045. It booted and guest services responded. Its original
configuration/checkpoint was retained; startup memory changed from 8 to 2 GiB,
dynamic minimum/maximum from 0.5/32 to 1/3 GiB, and virtual CPUs from eight to two.
Automatic checkpoints were already disabled and remain disabled.

The previously pending host proof completed at exact source `7442a800`; its three
source hashes match current bytes. The receipt records allocation error 112,
outside/descendant write denials, job/held-file retirement, helper exit zero and
removal of its own image. Independent inspection found the host scratch directory
absent. This is the 32 MiB host proof, not qualification of guest storage, a
512 MiB campaign, native compiler or interrupted active disk writing.

The new connection helper is fixed to the known host user and VM ID. It refuses
linked/oversized/invalid credential paths and existing credentials during setup,
requires successful guest identity checks before saving a credential, uses
Windows-encrypted Clixml outside Git, and closes sessions unless explicitly
returned. It makes no account, UAC, network, VM-state or elevation changes.
Refusal tests replace the prompt/authentication/VM-query boundaries with throwing
stand-ins and confirm that credential inputs are unchanged. Actual guest login
and successful credential storage remain unverified. The single interactive
setup window closed without a saved credential; no duplicate was launched.

The user will configure guest Codex administrator membership and global guest
UAC personally. No guest policy or account changes were applied by this work.
Verify those settings and the guest restart after the owner finishes. Other
agents may share the guest/account; cleanup must retire only owned processes and
workspaces. VM-wide stop/reset/reboot/compaction is not automatic cleanup.

Actual coordinator validation: 99 tests, no failures/errors, one existing
Windows PowerShell 5.1 execution-policy skip. The workspace runner reported
131,352 peak working bytes and successful removal. Source-map coverage remains
327 files; all 420 specification-manifest entries and the 891-entry sorted build
input list were checked. No normative spec or product source changed, so their
previous native/spec-suite evidence is retained at its original revision.

`.aide-local` contains zero file bytes after the inspected VM thumbnail was
removed with the reviewed cleanup helper. An earlier combined inspection/delete
command was automatically rejected before execution; the guarded cleanup helper
then removed the single 112,558-byte thumbnail with no skipped entries.
The guest's existing backing file grew 1,476,395,008 bytes between the recorded
start and inspection, before any DiskEd product test. Its cause is not diagnosed;
do not label dynamic VM storage free or erase a shared OS/checkpoint to reduce a
scratch count. Monitor shared OS growth as well as capped campaign output.

Next: owner completes setup/restart, then one local secure credential setup and
an actual PowerShell Direct read-only inspection of policy/token/toolchain/free
space. Prove the guest campaign's capacity and confinement before native work.
No guest/compiler/Win32 qualification, owner acceptance, main promotion or
release publication is claimed here.
