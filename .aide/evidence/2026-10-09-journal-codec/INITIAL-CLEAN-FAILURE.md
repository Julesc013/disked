# Initial clean campaign at 5293cf4e

The clean clone/configure/build succeeded at
`5293cf4e064427a1f54e9dc7942eea22e3837470`. The native campaign passed
47 of 48 groups, including the proposed journal codec, but failed
`image.shared_commands`: forty requests after the fixture's delayed callback
remained refused with `request_resource_limit`. This campaign is a failure,
not a fresh full-suite pass. Its exact commands and raw logs remain in
`reproduction-5293cf4e/`.

A separate timed probe observed timeout at 4.074 seconds and actual slot release
at 5.682 seconds. The unchanged shared-image group then passed three consecutive
runs (17.69, 17.68 and 17.73 seconds). These observations did not establish the
original failure's root cause or demonstrate a runtime correction.

The follow-up changes the private stdio fixture to test-owned local events: hold
the entered callback across timeout/refusal/cached requests, release it explicitly,
then observe slot availability with correlated requests. It preserves the required
unknown timeout, occupied-slot refusal, no unsolicited second reply and final
completion expectations. The ordinary product must ignore this private hook.
Release alone is not quiescence. Subsequent campaign results are recorded separately
against their actual source revisions. Raw logs and protocol snapshots retain
captured bytes in Git.
