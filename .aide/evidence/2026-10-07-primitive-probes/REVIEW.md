# Partial DE-W018 implementing-agent review

Reviewed `cca910c16635e1fe3cf9ff2729c006150100d258` against `635e846705cb1870608fecf292587bf25e997973` and the pre-implementation private probe
contract in tests/legacy/README.md. This is local implementing-agent review under
the continuation grant, not owner acceptance or historical target qualification.

- The width guards require 8-bit bytes, 16-bit unsigned short and an exact 32-bit
  intermediate. Each multiplication/shift widens before it can exceed a 16-bit
  intermediate; decimal division carries at most nine between limbs. No pointer
  or struct representation is copied into wire output.
- Parsing and addition publish a candidate only after all checks. Formatting,
  wire storage and text escaping check capacity before writing. Narrowing checks
  high limbs before assignment. Escaping is bounded to 256 bytes and 1024 output
  characters plus terminator, independent of locale and terminal capability.
- The native harness performs no explicit file/device operation. The Python
  coordinator writes ordinary local build/evidence files. There is no guest
  boot, disk mount, worker or elevated process in this control slice.
- The oracle uses Python integers and byte conversion instead of reproducing
  the limb arithmetic. CRLF is normalized to LF for scalar result comparison;
  terminal newline behavior is not qualified. Native sentinels verify refusal
  leaves outputs untouched.
  The same source and vectors pass all three clean compiler lanes; pointer widths
  differ while the exact u64 semantics agree. Actual 16-bit-int behavior remains
  a required later test, not an inference from C90 acceptance.
- The work record, canonical DE-051 owner and explicit required inputs bind the
  test contract, source and coordinator. Context tests keep their original
  assertions and independent refusal test. No context truncation was introduced.

Keep DE-W018 active. Complete qualified historical probe lanes where available;
retain missing environments as scoped blockers and continue independent modern
work when appropriate. Do not advertise legacy storage or product ABI support.
