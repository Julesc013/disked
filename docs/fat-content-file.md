# Held-source and contained FAT content

DE-W046 extends the existing FAT file provider and owned reader with an optional
content request. [The owning profile](../spec/catalog/fat-content-file-prototype.json)
defines expected behaviour before evaluation. No new public command is exposed.

The request contains a reference epoch, selected node, expected file size, byte
window/limits and comparison digest. The digest covers the exact prior observation
with only its transport capture epoch replaced by zero. Current native source
metadata remains a separate expected input. A digest or reference epoch authenticates
no source/process and supplies no opening grant.

The worker opens one ordinary local file and pins its parents, compares its native
generation before reading, captures metadata, and checks that digest before payload
I/O. Metadata and content use the same handle with write/delete sharing denied.
The validated content map determines every payload offset. It then rereads captured
metadata and payload pieces and checks native source metadata before releasing the
handle. There is no mount, source write, device enumeration or destination creation.

The original metadata receipt describes its initial capture/verification. The
optional `content` receipt describes the later window and recapture. Keep those
observation times separate. Complete payload bytes can remain inspectable when
their later verification disagrees; `observed_stable` then becomes false. Short
reads and native reader errors preserve only their actual contiguous prefix.
Repeated observations do not constitute an atomic snapshot or future freshness.

The parent reconstructs metadata and logical content from ordered copied regions,
checks source/window/request bindings, hashes, error/short outcomes and recapture
aggregates, then relies on the actual owned worker context to construct an immutable
snapshot. Pure frame validation alone establishes no worker provenance.

Existing 128-KiB input mapping, 8-MiB FAT payload, shared worker/process budgets and
retirement rules remain unchanged. Content-enabled frames alone permit a 393,216
character hex string; metadata-only frames retain their 32,768-character limit.
The request carries a digest rather than an entire earlier observation. Read
counts/bytes/chunks remain at most 512/196,608/4,096. Dynamic piece budgets are
checked after metadata capture and before payload callbacks.

Tests use generated ordinary files and separate normal/fault binaries. They check
exact payloads, Unicode source paths, source hashes, EOF/slack, held write/delete
sharing, cancellation with actual process exit, and independent rejection of
altered copied frames and altered publications from real fault workers. Controlled
holds/recapture changes are test fixtures, not hardware interruption qualification.

Public extraction, destination effects, coherent large traversal, mounted
consumers, other hosts, production recovery and full all-platform/storage 0.1.0
remain further work. Owner acceptance and release/storage privileges stay separate.
