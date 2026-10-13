# Recursive FAT extraction development

DE-W056 is active. Its [expected contract](../spec/catalog/fat-recursive-extraction-prototype.json)
requires a complete create-only ordinary-image destination backend, explicit
effect grants, original metadata evidence, native mapping/readback and contained
worker qualification. The current content and metadata primitives do not complete
that contract or expose a new public recursive-extraction command.

The private `providers/image/fat_tree_extraction.*` backend now prepares a
complete namespace without creating output, then requires a one-use grant for
its exact immutable definition digest. It binds source/code identities, selected
volume/copy, metadata policy, parent/entry commitments, prospective destination
and ledger locations, and explicit footprints/budgets. Preparation refuses
incomplete coverage, collisions, invalid mappings and unsupported paths.

Execution uses a new capture identity on the same held source and compares
original event/metadata commitments. It creates children atomically relative to
held parents using Microsoft's [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
`FILE_CREATE` contract. It opens no existing child as a creation fallback. Each
effect has a preceding flushed ledger intention; copied chunks are flushed and
read back before their checkpoints. Original records, slots, parents, allocation
and chunk observations remain in the ordered hash chain.

Valid explicitly interpreted metadata candidates are applied to new owned
objects and read back. Directory metadata waits until descendants finish;
file-ID ownership remains checked when creation time changes. Unspecified,
invalid and raw-only fields remain unapplied. The native timestamp handling
uses the [SetFileTime](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfiletime)
contract, with automatic access/write updates disabled on the copy handle.

Cancellation, faults and process interruption retain partial output and ledger
evidence. Existing resources remain untouched on collision. A flushed final
completion record remains completed when a later notification fails. The result
separates observed verified bytes from durable checkpointed bytes; ledger outcome
payloads label their counters before that outcome record to avoid circular hashes.

The backend remains private. The Windows process adapter now uses the shared
owned host and existing worker limits for separate prepare/grant/execute phases.
Copied definitions and outcomes bind the actual process/code/request epochs;
prepared source and dependency handles persist in the same child while waiting
for the exact grant. A bounded anonymous payload has disjoint publication/grant
slots. Progress and result publication do not prove exit.

The controller pins source and resource ancestors until actual exit. Cancellation
and owned-job retirement do not drop a running owner's dependencies; an unresolved
destructor transfers its preallocated owner to a passive retained list. Reaping
requires observed exit. Old reader profiles retain their claims and limits; the
compiled writer capability itself grants no mutation authority.

Independent retained-history inspection and the complete exact-source native
campaign still remain before DE-W056 can finish or a frontend can invoke
recursive mutation. No persistent reconnect or production/storage privilege
admission is supplied by this process-lifetime prototype.

`runtime/capture/fat_content_stream.*` continues one observed file's allocation
and content in bounded pages. `providers/image/fat_tree_file.*` admits content
only from its own latest held-source traversal page. Those preserve the existing
source/capture/epoch and no-slack rules; imported frames do not grant access.

`runtime/acquisition/fat_metadata.*` reparses the exact original short record and
long-name slots. It keeps raw OEM bytes, UTF16 units, slots, attributes and times
separate from output candidates. It opens no files and writes no metadata.

`FatTreeFile::metadata_candidates` selects a file/directory record from the
adapter's latest page, then double-reads its exact short record and each original
long-name slot through the same held source. Its frame binds the original parent
key, process/capture identity, source generation and read/applicability receipts.
Unknown/stale keys and observed cancellation cannot produce a mapping frame.
This is synchronous preparation; it still needs the recursive operation's
contained worker, output grants, writer lifetime and destination readback.

| Explicit policy | Meaning |
|---|---|
| `long_or_short` | Use valid associated canonical long-name slots when present; otherwise decode the short alias. Invalid supplied slots are refused rather than silently choosing another name. |
| `short` | Choose the short alias explicitly while retaining original long slots. |
| `identity` | Choose `entry_<source offset>` explicitly. This synthetic name does not claim to restore the original name. |
| Unrepresentable name: `refuse` / `identity` | Refuse the entry or apply the explicitly selected synthetic mapping. No replacement, normalization, truncation or collision suffix is implicit. |
| `preserve_raw` | Keep original FAT times without supplying native time candidates. |
| `fixed_offset` | Interpret valid source-local fields using an explicit offset east of UTC, from −840 to +840 minutes. It supplies candidates, not a metadata application claim. |

Creation retains 10 ms fractions; write retains 2 s precision; access is a date
interpreted at source-local midnight. Unspecified and invalid fields remain
unapplied. Original fields remain available even when another field is valid.
Read-only, hidden, system and archive bits are native candidates; the destination
object's type comes from its own creation. No Unix ownership or absent FAT
metadata is invented.

`providers/image/fat_native_metadata.*` supplies the Windows OEM decoder for
explicit CP437 and CP850 in this private lane. It checks invalid input, disables
best-fit output and requires exact byte roundtrip. These choices follow the
[MultiByteToWideChar](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-multibytetowidechar)
and [WideCharToMultiByte](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte)
contracts. Other encoding profiles need their own implementation/evidence;
this does not narrow the broader project scope.

The private backend now establishes original source/tree membership, parent
identities, selected-name collision checks, its immutable definition/grants,
create-only effects, ordered original evidence and native application/readback.
Contained writer admission, independent retained-history inspection and complete
exact-source qualification remain. Candidate names/times or imported matching
hashes authorize no new effects. Existing raw/logical plans and selectors retain
their versions.

Build the private probes and selected standalone headers in the recorded Windows
development build, then run `acquisition.fat_metadata` with CTest. This group's
independent expectations cover original name representations, malformed mappings,
FAT calendar/precision and every byte of the two selected native code pages.
It does not exercise destination creation, physical media or another platform.
