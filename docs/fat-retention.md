# Retained FAT metadata captures

DE-W044 adds an in-process retention prototype to the Windows image/fake
composition. Its native qualification is pending. The exact contract is
[fat-retention-prototype.json](../spec/catalog/fat-retention-prototype.json).

`image inspect --view fat --retain-capture yes` retains the independently verified
metadata frame, native context and final worker observation. The response includes
`capture_retention` with an ID, byte length, SHA-256 and `current-process` lifetime.
The default is `no`; ordinary inspection retains its previous response shape.

Retained data belongs to the running invocation. Use a persistent stdio, shell,
TUI or GUI session to retrieve it. A separate executable invocation has a separate
store. A one-shot CLI retention receipt therefore expires when that process exits.

| Command | Behaviour |
|---|---|
| `image capture inspect` | Lists at most four reserved/retained entries and their originating request IDs. |
| `image capture inspect --phase read --capture-id ID --byte-offset N --byte-count COUNT` | Reads up to 196,608 exact bytes from an immutable retained record. |
| `image capture release --capture-id ID` | Releases a retained entry; subsequent reads refuse unknown. |

Read responses use `hex-json-utf8`: decode the lowercase `data` hex and concatenate
chunks at their declared byte offsets. Check each chunk hash, complete record hash
and length before decoding the reconstructed UTF-8 JSON. `next_offset: null` means
EOF. Offsets are byte offsets and may split a UTF-8 character. An offset exactly
at EOF returns an empty chunk; an offset beyond EOF refuses the request.

The record contains the original frame, including raw captured metadata regions,
full observations omitted from the display projection, native context and worker
observation. It does not contain unobserved file payload. Retrieval does not reopen
the source and does not establish current source freshness, an atomic snapshot,
durable custody, mounted filesystem compatibility or storage authority.

Each reserved/retained entry has an eight-MiB encoded-record limit. Four slots
reserve at most 32 MiB; entries are never automatically evicted or assigned reused
IDs. A full store refuses another capture before source access. Oversized, refused
or unresolved captures release their reservation after the source callback returns.
Honest captured partial/changed observations may be retained with their failed
inspection outcome and uncertainty intact.

A frontend timeout does not release a running callback's reservation. List can
show that reservation and later completion under the original request ID. Release
of a reserved entry refuses busy. Late completion produces no unsolicited second
stdio response. The store is shared independently of frontend object lifetime.

This prototype adds no physical-device access, installation, elevation, production
writer/recovery admission or full 0.1.0 qualification.
