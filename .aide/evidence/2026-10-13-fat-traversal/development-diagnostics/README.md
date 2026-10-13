# Working-tree diagnostics

The first focused run failed two fixture expectations: deleted records have
original raw bytes but no decoded live attributes, and 20 records did not fit the
single FAT32 root cluster supplied by that fixture. The oracle now explicitly
checks the deleted zero-value interpretation plus original bytes; the FAT32 root
uses an actual two-cluster chain. Later focused runs preserve all tests and pass.
Review also found that the checked-region source label is limited to 128 bytes
with no embedded NUL. Constructor checks now reject contradictory labels with a
typed error before callbacks, and native tests cover those refusals. Contradictory
directory metadata cannot authorize descent. Original pending name/boot fragments
are retained on interruption. These are development logs, separately attributed
from the exact clean native source qualification.
