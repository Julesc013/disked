# Implementer review: retained FAT frames

Reviewed per-process store ownership, lazy native nonce, bounded monotonic IDs,
reservation-before-source ordering, immutable UTF-8 bytes and exact frame/result/
native-context binding. Receipt preflight and exception-safe store commitment
preserve quotas; refused/unresolved/exceptional callbacks abandon after return.
Timeout does not imply callback retirement. Shared ownership outlives frontend
objects; late completion is available by original request correlation without an
unsolicited second wire reply. Release denies new retrieval; admitted shared bytes
remain alive. The bounded hex transport preserves arbitrary UTF-8 byte boundaries.

Reviewed default-no compatibility, producer/presentation budgets, canonical scalar
validation, metadata/source uncertainty and product/probe isolation. 101 native
groups and the complete tooling suite pass at 4d3dc0a3. This is implementing-agent
review, not independent-person/owner acceptance or full 0.1.0 completion.
