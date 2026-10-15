# Protected NTFS index blocks

DE-W088 implements the private supplied-byte INDX header, update-sequence checks,
separate-buffer restoration and existing entry cursor. Its [execution contract](../spec/catalog/ntfs-block-prototype.json)
defines outcomes before implementation and evaluation. The working 1,230 guarded INDX cases, 964 existing FILE cases, 1,502 filename/index
cases and strict C90 checks pass. Clean full-suite qualification remains pending. No source-bound directory acquisition or full NTFS qualification is inferred.

FILE and INDX share only the actual tail/disjoint-buffer mechanics; format-specific
headers retain separate owners. The original all-platform/storage 0.1.0 and separate
owner, privilege and release gates remain.
