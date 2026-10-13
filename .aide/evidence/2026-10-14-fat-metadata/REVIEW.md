# Agent review of partial DE-W056 metadata preparation

The runtime mapper reparses original short records and long slots through the
existing portable decoder, preserves raw representations and separates them
from explicit output candidates. It bounds record/slot/component sizes, checks
UTF16 and native forbidden/reserved names, and refuses unknown encoding or case
mapping instead of guessing. Synthetic names require the explicit policy and
are marked separately. Calendar conversion distinguishes valid candidates,
unspecified/invalid fields and raw-only preservation; independent datetime
expectations cover 1980, leap-year/2100, precision and offset boundaries.

The Windows decoder has explicit CP437/CP850 identities, invalid-input refusal,
no-best-fit output and exact byte roundtrip, checked against an independent codec
for every byte. Neither conversion nor the runtime mapper opens a source or
changes metadata. The existing held-file adapter supplies membership from its
own latest page, double-reads the exact record and original slots, checks native
applicability around each region and before publication, and retains source/
process/capture/parent receipts. Cancellation callbacks clear on exceptions and
have their own diagnostic. Fault and normal dependency separation still passes.

The placement is coherent: runtime/acquisition owns preservation/mapping policy;
providers/image owns Windows output conversion and ordinary-source identity.
No source-root restructuring, new public extraction command or promoted ABI is
introduced. Tests prove preparation and relevant regressions, not a destination
writer, applied/restored metadata, native collision proof or full qualification.
Continue within active DE-W056 to the complete destination/effects backend.
Owner acceptance and later storage/release gates remain separate.
