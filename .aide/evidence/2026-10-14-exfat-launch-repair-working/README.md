# Partial reader launch diagnostic and ownership repair

The adapters now retain worker_files::Failure.platform so actual launch errors
are inspectable. The FAT source is declared before the worker outside the try
block, keeping its pins alive while catch paths establish actual worker exit.
The retention fixture closes owned protocol sessions before temporary-file
cleanup. Existing expected outcomes remain unchanged.

The current working build passes68FAT retention cases and33exFAT command cases,
two standalone reader headers, structural/context/manifest/source-map checks.
Source/build/artifact identities are retained. The source lifetime correction
has source inspection and these regressions, not a new post-spawn exception
injection qualification. No new242-tooling or full-native pass is claimed.

Earlier exact60376a0e ran140groups with eight failures. Improved diagnostics show
Windows error5 in that campaign's Release directory, while byte-identical copies
elsewhere run. The extended launch cause and all eight groups remain unresolved.
This partial repair does not qualify the normal composition or promote main.
Original full0.1.0, owner/platform/storage/release gates remain open.
