# Private held-file exFAT observation

DE-W068 connects the [root/system observer](exfat-capture.md) to actual ordinary
Windows image files. The [owning profile](../spec/catalog/exfat-file-prototype.json)
defines its bounded scope. This synchronous adapter is private and requires
contained-worker qualification before use by shared frontends.

`providers/image/exfat_file.*` reuses `local_file.*` for ordinary-file checks,
read-only sharing, exact path binding and pinned ancestor generations. It does
not change those shared rules. Input limits, checked windows and the signed
native seek range are validated before opening; actual size and metadata come
from the held file. Invalid paths, devices, aliases and reparse points have no
fallback or elevation path.

Ordered responses retain requested offsets/lengths, actual bytes, platform errors
and whether a read was attempted. Failed binding/cancellation checks before a
read record a refusal rather than pretending that a kernel read failed. The
runtime observes those responses and rereads within its finite budgets. Pure
replay requires the same request order and complete result. No borrowed bytes
escape through the returned owned observation.

Before/after source metadata, ancestor generations, actual process ID/creation
and a provider-scoped sequence bind each capture. Metadata disagreement, late
binding failure or replay disagreement withdraws applicability while preserving
measured prefixes and errors. Cancellation-predicate exceptions have a typed
failure. Repeated metadata/byte agreement remains live, uncoordinated evidence;
it is not atomicity, future freshness, physical identity or renewed opening rights.

Failure callbacks compile only into the separate fixture library and probe.
Normal builds do not expose a fault environment protocol. Tests exercise actual
generated files, byte preservation, exact retained-region replay, held access
denial, malformed images, limits, cancellation and late binding failures.
Actual junction/hardlink checks are distinct from a file-symlink fixture; a host
that cannot create the latter records it as unverified and does not elevate.

This work does not admit tree traversal, file extraction, physical devices,
production writers/recovery, other hosts or the full original 0.1.0 release.
Next qualify the existing contained-reader host with these owned observations,
then paged namespace/tree/content and ValidDataLength handling.
