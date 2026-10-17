# Authorized local storage setup

Base: `d103a302fbc234de940033c45b070361ca31fa22`.
Source: the user's explicit answer to the execution-setup question on 2026-10-17.
The continuing full 0.1.0 goal is active. Historical blocked handoffs describe
their own earlier revisions and remain valid history.

The question proposed a new blank fixed 512 MiB image at
`D:\Projects\DiskEd\scratch\disked-work.vhdx`, first tested at 32 MiB, together
with OS worker write restrictions. It explicitly noted possible setup elevation
and excluded physical devices, product installation and budget increases.

The user answered "thats fine" and authorized scratch files/disks and use of this
existing Windows 10 VM for DiskEd testing after cleanup, while protecting other
concurrent users. The user requires deletion after use and retention of only
necessary, compact compressed evidence. This is an execution grant; it is not
owner acceptance, release approval or proof of a working storage boundary.

The limits remain 32 MiB of local metadata, 1 GiB aggregate disposable storage,
20,000 entries and 20 GiB free on each host backing volume. Do not interpret the
grant as permission to increase those limits or provision another large VM.
The capped scratch filesystem's capacity is separate from the host reserve.

Initial AppContainer checks with tiny owned fixtures establish that a worker can
write inside its work directory, receives access denied outside it, and passes
that restriction to its child. Job closure retires the worker and descendant.
The temporary package profile is redirected into owned work and removed at the
end. Eight actual Windows tests pass; see `storage-final-tooling.log`. These
tests use ordinary host storage and establish **no filesystem capacity ceiling**.

The 32 MiB virtual-disk proof uses a reviewed, fixed-path
setup helper. Only that helper can request elevation; product/test workers remain
unelevated. Its inputs contain no physical source, caller-selected disk number
or arbitrary command. It binds initialization/formatting to its own newly
created image and retires it after a nonce-bound release or a finite lease.
The ordinary user-context attempt created and removed its 36 MiB backing file;
mounting failed with required-privilege error `0x80070522`. The first elevation
request did not complete and its identified controller was retired. Windows UAC
completion is separate from the grant and may require interaction at the VM
console. Until actual allocation-denial and mounted cleanup results exist, keep
the native campaign gate unsatisfied. No 512 MiB setup, compiler qualification,
upstream AIDE runtime or DiskEd feature qualification is implied.
