# Repair and requalification boundary

The owner answered the 2026-10-21 native-gate question: **continue repairs and
requalification, then merge into main and pause; this needs more time**.
The four failures at source `54bc8cd8a844344336ce8485202a108e5c04d784`
remain retained in `full-native/`. That run is not a passing integration gate.
Dev checkpoints are authorized; main promotion requires the passing current
native gate. No release or tag is authorized.

## Diagnosis before changes

`gui_fixture.caption` first queries WM_GETTEXTLENGTH and then reads WM_GETTEXT
into that exact allocation. The control can change between those messages.
This permits a valid growing response to be truncated, consistent with the
JSONDecodeError in `frontend.fat_tree_sessions`. Replace that two-message
acquisition with one bounded WM_GETTEXT read, preserving the existing 1 Mi
UTF-16-unit limit and a sentinel unit to detect over-limit content. Exercise
growing text, the exact boundary and over-limit text independently of a live GUI.
Malformed JSON must still fail; the fix must not catch and discard parse errors.

The buffer and return-count interpretation follows Microsoft's
[WM_GETTEXT](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-gettext)
contract. [WM_GETTEXTLENGTH](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-gettextlength)
describes an observation of length, not an atomic binding to a later read.

The `frontend.gui_windows` 3,000 ms message timeout, `image.fat_commands`
4,000 ms request wait and `image.fat_retention_commands` 1,000 ms worker-start
timeout are observations, not established root causes. Do not attribute them to
the text race or guest load without further evidence. Rerun the four original
groups with their unchanged assertions, deadlines, fixture inputs and production
wait policy. Preserve any further failure and its original diagnostics.

## Evaluation declared in advance

1. Run the bounded host regression for text acquisition.
2. Build the exact committed source in the existing confined guest profile and
   run the four affected original CTest groups. This focused result cannot
   replace the full gate.
3. Run the complete current x64 composition: all 180 groups, 69 standalone
   headers, 14 executable/import observations, actual GUI evidence review,
   closed archive verification and owned cleanup. Keep the 512 MiB filesystem,
   1 GiB aggregate disposable budget, original build/group/campaign limits and
   required observations unchanged.
4. Complete applicable metadata checks and agent review. Record exact evidence
   applicability and any unreproduced failures without claiming their causes
   were fixed. Merge the verified dev checkpoint into main, verify remote refs,
   and pause for continuation on another machine. Do not begin a new feature.

Any Win32 claim remains limited to its exact retained revision and private
slice. These repairs do not confer provider, physical-media, owner or release
acceptance.

## Focused attempt and next evaluation

At `a8b013b6`, all three FAT groups passed, as did seven of eight GUI methods,
including the earlier message-timeout case. The last GUI method could not start
its guard/dependency-unavailable companions: the focused target selection had
omitted `disked_provider_guard` and `disked_gui_unavailable`. That is a campaign
setup error, and the focused attempt remains failed. Both companions are now
explicit in the focused selection. No assertion or deadline has changed.

The next evaluation uses the complete existing 14-executable composition and
all 180 original groups, including the four repair groups. It supplies both
companions and advances the required full gate in one clean build. It does not
relabel the incomplete focused attempt as passed or combine different builds
into a fictional complete run. The separate FAT timeout causes remain
unestablished; their non-recurrence in this attempt is recorded as such.
