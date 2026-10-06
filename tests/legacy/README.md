# DE-W018 primitive probe contract

These harmless probes compare a private C90 implementation across available
compilers. They are not the DiskEd command parser, a storage provider, or a public
SDK ABI. They accept explicit argument strings and write results to stdout; they
do not open files, enumerate devices, elevate, create workers or modify terminals.

The common representation uses four least-significant-first 16-bit limbs, eight
8-bit octets and an exactly 32-bit unsigned intermediate selected from limits.h.
Compilation rejects unsupported widths. Pointer width and struct layout never
define a serialized address. No native 64-bit type is required. The test launcher
records actual char/short/int/long/pointer widths independently.

Define these outcomes before implementation:

- `roundtrip <decimal>` accepts canonical ASCII decimal 0 through
  18446744073709551615, prints `ok <decimal> <16 lowercase little-endian hex digits>`.
  Empty, signed, whitespace, leading-zero and nondecimal values return exit 2,
  `refused invalid`. Values beyond u64 return `refused overflow`, exit 2.
- `add <decimal> <decimal>` uses the same parsing, prints the exact sum and bytes,
  or refuses overflow without changing the output value.
- `narrow <decimal>` prints `ok <decimal>` only through 4294967295; greater values
  return `refused width`, exit 2. No silent truncation.
- `wire <16 hex digits>` decodes exactly eight little-endian bytes and uses the
  same exact decimal/hex output. Odd, short, overlong or nonhex input is invalid.
- `escape <0..256 bytes as hex>` prints `ok ` followed by inert ASCII display:
  printable ASCII except backslash is literal, backslash is doubled, and every
  other byte is uppercase `\xHH`. Input bytes remain unmodified. This is a byte
  display probe, not Unicode decoding, normalization or filename conversion.
- Caller-owned outputs stay byte-for-byte unchanged on refusal. Decimal output
  includes a NUL terminator; insufficient capacity refuses before any write.
  Input and output objects may alias for addition. In-place text/wire conversion
  is outside this probe contract. Null pointers are outside its C call contract.

The independent Python integer oracle exercises boundary and seeded random
decimal/addition/wire cases, invalid syntax, width refusal, full byte escaping,
buffer boundaries and unchanged outputs. The C harness checks refusal sentinels;
the oracle supplies expected values independently of the limb implementation.

Modern control lanes use installed GCC in strict C90 mode and installed MSVC in C
mode. Each result retains exact commands, compiler path/hash, source hashes, PE
imports, host, artifact hash and actual launch outputs. Historical 8086, Win16,
Win9x and OS/2 lanes require their own compiler/SDK, executable/CPU/memory model
and actual launch environment. Missing tools are explicit scoped blockers;
registered VM names or successful modern builds do not qualify those lanes.
The shared DiskEd parser corpus is `not_run` until a target parser is admitted.
