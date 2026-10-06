# Initial findings and corrections

The first native reader run passed 1291 synthetic cases and the memory-boundary
probe. Implementing-agent inspection then identified a missing combined
observation: a later EBR block inside earlier logical data still needs the
metadata-overlap flag even when that EBR has a bad signature. Detection now occurs
before the content early return, with an explicit regression case.

The first GCC build compiled the C90 reader and primitives cleanly, then rejected
two existing JSON harness statements under -Werror=misleading-indentation.
Separating the increments onto their own lines preserved the behavior and the
warning policy. The next GCC build passed all then-current 1292 cases and the
native guard test. MSVC 2017 x86 also passed those 1292 cases on this modern host.
Two additional address-widening/budget cases and an oversized-feed state check
bring the final corpus to 1294; final source-bound results supersede these earlier
working observations, which are retained.

The metadata preparation helper initially used the Windows default text encoding
for a UTF-8 document and failed before editing that document. It resumed the
remaining document/evidence suffix using explicit UTF-8. That replay duplicated
one already-written explanatory paragraph; review removed the duplicate from
the publication and its template before the final manifest was generated. This was a coordinator read failure,
not a product test result. Direct upstream HTTP failures and the stopped public
Git tag read are recorded at start; the public API resolved the exact Linux tag.

No installed external partition parser was found by the narrow PATH query for
mmls/fdisk/sfdisk/parted. The corpus independently constructs absolute layouts,
then encodes relative entries; it is not a run of an external differential parser.
Coverage fuzzing, historical layouts, real media/source-consistency and the full
DE-REQ-032 reader/provider programme remain open beyond this bounded work unit.

Final review found a hybrid-classification defect for zero-count EE records:
a standalone malformed protective record was labelled hybrid, while adding an
ordinary active partition could lose that flag. Two new cases reproduced both
wrong results. Classification now counts ordinary active entries separately from
protective records. The final corpus is 1296 cases. The working 35-group run
preceded this correction; targeted checks and the clean full run follow it.

The test receipt now uses the completed unittest result, including failed
subtests, rather than emitting a literal passed=true at the end of a test method.
The two-failure run against the old executable is retained as a positive control:
exit 1 and passed=false. The earlier passing receipts correspond to actual
passing runs; the first failing probe did not request an evidence JSON file.
