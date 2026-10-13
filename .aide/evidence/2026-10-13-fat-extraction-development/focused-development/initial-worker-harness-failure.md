# Initial development harness failure

The first direct CTest run of `image.fat_extraction` failed the contained-worker
test while the file/pipeline cases passed. The harness stopped on a completed
observation read and attempted to index a still-null logical outcome:

```text
TypeError: 'NoneType' object is not subscriptable
```

Its premature temporary-directory cleanup then encountered a sharing violation
on `state/acquisition.cancel`. These are retained diagnostic observations from
the tool output, not a byte-for-byte copy of its full log or a qualification run.
The harness was corrected to inspect the operation's finished phase and wait on
the actual owned process before cleanup. The extraction requirements and native
retirement bounds were preserved. Subsequent focused tests passed.
