# Partial implementing-agent review

The pure cursor revalidates all retained record bytes, binds a fixed header and
worker domain, and preserves the old canonical LF hash chain. One-based event
cursors make default replay include the zero-based admission record. Positive
resumption cannot silently accept changed/shortened prefixes. Event budgets and
sink failure close only the observer. Cursor commit after sink admission uses
preallocated digest swap; it does not allocate after a successfully admitted event.

The native adapter exports a history only after actual store/control identity
checks. Retained declarations and current process facts are separate. An intact
saved exit can be observed historically even when current process code cannot
be queried; its diagnostic remains visible. Known birth/code conflicts stop
active observation. Unavailable facts can be reobserved within finite bounds,
never treated as a grant or writer restart. Cancellation’s live-owner requirements
remain intact. The same existing detached owner persists through client changes.

Three focused native groups and tooling pass; full common command/frontend,
compatible-reader, exact-source, owner and release admission remain. This is
implementing-agent review, not independent owner approval or full work acceptance.
