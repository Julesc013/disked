# NTFS table inspection

DE-W102 adds `image inspect PATH --view ntfs-upcase --volume-offset OFFSET
--volume-bytes BYTES`, using the existing owned ordinary-image reader. The
[execution contract](../spec/catalog/ntfs-upcase-command-prototype.json) defines
the expected command and projection before implementation.

The view preserves the complete observed 128 KiB table as eight ordered hex chunks.
Each string fits the existing protocol limit. The table retains its source,
capture, volume and FILE 10 identity and digest. Bounded metadata prefixes keep
original-array hashes and explicit omissions. A complete table observed before a
later source disagreement remains evidence with no applicability or effect grant.

The command shares existing CLI, stdio, GUI, TUI and shell actions. It does not
establish namespace ordering, semantic Unicode correctness, lookup, content or
current-source authority. No new production file, source opener or worker host is
needed. The original platform, storage, owner and release gates remain separate.
