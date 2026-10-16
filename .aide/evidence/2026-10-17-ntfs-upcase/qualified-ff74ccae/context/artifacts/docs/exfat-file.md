# Private held-file exFAT observation

DE-W068 connects the [root/system observer](exfat-capture.md) to actual ordinary
Windows image files. The [owning profile](../spec/catalog/exfat-file-prototype.json)
defines its bounded scope. This synchronous adapter is private and requires
contained-worker qualification before use by shared frontends.

DE-W072 adds typed `ExfatUpcaseFormat` overloads returning private file-capture/2.
Automatic interpretation carries root-observation/2; typed explicit interpretation
carries root-observation/1. Existing boolean overloads retain file-capture/1.
They share source binding, limits and retained-response replay. The
[command profile](../spec/catalog/exfat-command-prototype.json) owns this extension;
its new evidence is separate from W068's revision-bound qualification below.

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
The contained reader has a separately qualified explicit-format baseline.
Current work verifies automatic v2 transport and common frontends, then paged
namespace/tree/content and ValidDataLength handling.


DE-W068's available ordinary-file scope reaches local agent review at exact
`c73c6870`: 60 native cases/seven methods, 20 selected regression groups, one
header, normal/fault imports/context/source hashes and 242 tooling tests with
two skips pass. Actual file-symlink creation remains unverified without privilege;
leaf/ancestor junction and hardlink checks pass. The clean sparse checkout contains
every registered/build input and current source/tests/spec/docs/tools/external
files, excluding unused historical evidence. No fresh full native-suite or archive
checkout claim. Repository evidence: `.aide/evidence/2026-10-14-exfat-file-qualified/`.
Contained worker, coherent namespace/tree/content and original full0.1.0 remain.
