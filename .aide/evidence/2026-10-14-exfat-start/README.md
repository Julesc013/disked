# exFAT expected execution contract

DE-W057 clean qualification is integrated on main ed5a091b with owner acceptance
separate. DE-W058 selects private supplied-byte exFAT boot/geometry/checksum and
allocation metadata, reusing portable checked/view primitives. The expected
contract is spec/catalog/exfat-reader-prototype.json, based on the official
Microsoft exFAT specification sections3/4 inspected14October2026. No fetched code
is executed or adopted. Broader formats/platforms/storage remain within0.1.0.

This stage records boundaries/expected outcomes before evaluation. Specification
and context freshness checks pass. Native implementation/tests are not_run;
no bitmap/upcase/directory/traversal/provider/mount/TexFAT/writer claim follows.
Next: implement C90 decoder and independent generated-byte oracle, then qualify.
