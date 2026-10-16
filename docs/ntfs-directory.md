# Source-bound NTFS directory indexes

DE-W089 connects the supplied-reader bootstrap and stream closure to resident and
nonresident directory indexes. The [execution contract](../spec/catalog/ntfs-directory-prototype.json)
defines exact reference/name/mapping/bitmap/graph/quota outcomes before implementation
and evaluation. The working collector passes 227 guarded cases, including multi-level
indexes, bitmap/extension closure, malformed inputs, quotas and exact read traces.
Existing bootstrap/closure/stream groups and the build boundary checker pass.
Clean full-suite and selected Win32 qualification remain pending.

This is private source-context acquisition and framing. Native file/worker/frontend
admission, full namespace/content, collation and the original platform/storage
0.1.0 remain separate required work. No storage effect or owner acceptance follows.
