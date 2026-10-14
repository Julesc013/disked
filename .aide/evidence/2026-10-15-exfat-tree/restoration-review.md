# Restoration lifecycle correction

The original exact full campaign failed at preparation, and a same-artifact rerun
failed at execution and the subsequent kill wait. Neither establishes why native
I/O was delayed. The harness then tried to remove an in-use backup, obscuring the
original failure and threatening dependencies needed to inspect its outcome.

The DE-W024 regression correction drains both pipes, records named waits and
process/reader state, preserves the original exception and retains the fixture
on failure. A requested kill does not count as exit. Cleanup requires confirmed
exit and a normally completed test. All15-second reply and five-second termination
waits remain unchanged, as does the300-second restoration group limit.

Five focused harness regressions pass, including a child that stays live after a
reply timeout and a synthetic unconfirmed termination. An opt-in private native
I/O trace run passes138 restoration cases with271 confirmed process exits. The
default execution/restoration/harness groups pass; their inspection companion
initially fails because it imports the removed reader helper. Updating that
caller to the same diagnostics/retention lifecycle then passes121 inspection
cases. The initial failure remains in the evidence. No expected storage result
or default stderr assertion was relaxed.

These working results justify an immutable full144 campaign. They are not a
diagnosis or proof that the earlier native delay has been eliminated, nor product
writer/recovery admission, power-loss qualification or owner acceptance.
