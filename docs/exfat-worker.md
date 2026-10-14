# Private contained exFAT reader

DE-W069 runs the [held ordinary-file adapter](exfat-file.md) through the existing
`ObservationWorker`. The [owning profile](../spec/catalog/exfat-worker-prototype.json)
defines its private scope. It introduces a compiled exFAT profile and strict
frame verification, without another scheduler or storage-effect authority.

Input binds an exact capture epoch, path, expected native metadata, window,
upcase representation and finite limits. The held adapter compares expected
metadata before its first content read. The parent reconstructs W067 observations
from ordered retained responses and checks source/process/sequence relationships,
limits and aggregate flags. Payload hashes establish byte agreement; actual owned
PID/creation, attempt/worker/observer epochs and code/request identities are still
required before constructing the immutable typed snapshot.

Normal roles reject fixture keys. Separate compiled fixtures exercise startup,
reply, payload, region, metadata and process contradictions, hangs, late replies,
cancellation and abrupt exit. Native prefix captures remain inspectable without
becoming complete source, lookup or writer claims.

The shared host's retirement flag now comes from the same owned-process
observation returned to the caller. A successful termination request or zero-wait
timeout does not mark a running process retired. Publication and process exit
remain distinct, and retained values can be inspected after retirement without
renewing source access. Callers retain the owned session while exit is unresolved.

Exact full clean `cce05d17` passes all 139 current native groups, 69 reader
cases/six methods, 63 file cases/eight methods, standalone headers/imports/
context/source checks and 242 tooling tests with two skips.
[Retained evidence and local review](../.aide/evidence/2026-10-14-exfat-worker-qualified/README.md)
cover the shared retirement change; original failed working runs remain retained.
The unavailable file-symlink fixture remains recorded separately. Frontend,
paged namespace/tree/content, other-host, physical writer/recovery, owner and the
full original platform/storage0.1.0 release remain separate and unfinished.
