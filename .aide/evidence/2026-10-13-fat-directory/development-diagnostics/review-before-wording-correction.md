# Implementer review: FAT directory/name observations

Reviewed C90 raw-record decoding, complete-set name correlation and display
against the predeclared profile. Exact representations and unknown metadata
remain distinct from interpreted fields, encoding, canonical text and lookup.
Shape/order/checksum failures do not create an associated name. An eight-bit
collision remains a format correlation, not authentication. Cluster/time issues
do not erase separately established name-byte correlation or grant file access.
Original Unicode units are never normalized or substituted; ASCII display cannot
emit terminal controls. Fixed budgets and output-before-validation behavior are
covered by independent fixtures and protected memory.

The exact clean build, 6,790 new cases, previous 1,335 allocation cases, 89 native
groups, eight headers and tooling regression pass. GCC 15.2 checks strict C90
syntax only. The collision-fixture correction keeps the original expected
correlation rule; its failure is retained. No production writer, provider, command
or effect path is introduced. This is one implementer review, not owner or
independent-person acceptance. Continue traversal, allocation/extraction and
provider/frontend work within the full all-platform/storage 0.1.0 programme.
