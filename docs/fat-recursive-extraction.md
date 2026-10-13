# Recursive FAT extraction development

DE-W056 is active. Its [expected contract](../spec/catalog/fat-recursive-extraction-prototype.json)
requires a complete create-only ordinary-image destination backend, explicit
effect grants, original metadata evidence, native mapping/readback and contained
worker qualification. The current content and metadata primitives do not complete
that contract or expose a new public recursive-extraction command.

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

The native backend still must establish original source/tree membership, parent
and sibling identities, path/name collisions, the immutable effect definition,
grants, create-only effects, original ordered evidence, actual application and
independent readback. Candidate names/times and matching hashes authorize none
of those effects. Existing raw/logical plans and selectors retain their versions.

Build the private probes and selected standalone headers in the recorded Windows
development build, then run `acquisition.fat_metadata` with CTest. This group's
independent expectations cover original name representations, malformed mappings,
FAT calendar/precision and every byte of the two selected native code pages.
It does not exercise destination creation, physical media or another platform.
