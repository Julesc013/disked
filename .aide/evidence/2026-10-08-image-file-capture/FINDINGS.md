# DE-W024 file capture findings

The initial generated-file test stopped at the directory case: the source open
returned image_source_open with Windows code 5 instead of the specified typed
image_file_type. The terminal command exited 1; its tool response was observed,
but no raw file log was retained. The adapter now opens the final path with the
directory-inspection flag and rejects its type explicitly before reading.

The next test run exceeded its 180-second enclosing runner deadline. Process
checks confirmed the same live test handle before it ended; it was not restarted
merely because polling returned no output. Its sparse fixture was found extended
only to 5,129,957,376 bytes rather than the intended 8,590,065,664. The test's CRT
truncate path was filling the extension. Diagnostic case/stack output was added;
the fixture now uses explicit Win32 sparse length extension. The deadline was not
relaxed and the intended large-image checks were preserved. Diagnostic results
and any subsequent failures are retained in their command logs.

The source map readers are unchanged. Source paths, metadata, coverage, reread
errors and interpretation findings have separate meanings. A successfully parsed
map and equal rereads never establish an atomic snapshot or writer authority.

The first overlap-control fixture put a GPT array at its own header LBA. The C90
reader correctly refused that inconsistent header before requesting the array;
there was no overlapping capture for the test to change. Diagnostic and
verification logs retain the failed assertion. The replacement fixture keeps a
valid GPT array and places an eligible MBR extended root inside its region,
so distinct requested views really overlap. Its assertions remain unchanged.

Adding per-case output exposed a cp1252 console encoding failure for the emoji
filename case. Diagnostics now print an ASCII representation; the actual Unicode
path and its returned original/resolved forms remain unchanged and are tested.
The diagnostic-encoding-correction run passed 104 file cases and 75 map cases.
The subsequent source-bound verification must recheck the final receipt fields.
