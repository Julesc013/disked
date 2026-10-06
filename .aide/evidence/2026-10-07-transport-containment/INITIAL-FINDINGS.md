# Transport containment findings

The prior clean executable (source ee7cfb6984c1049cad3b3bdc53fa615687c4f244)
remained blocked after 4.5 seconds with an unread stdout pipe. Draining the pipe
then yielded the complete 21,800-byte command response and exit 0. The retained
baseline JSON distinguishes an observation timeout from process completion.

The initial output-waiting run passed four of five tests. The prefix test failed:
it expected exit 4 after reading 128 bytes, but observed exit 0. Python's default
BufferedReader had read ahead. An explicit comparison observed the full response
with buffering, while bufsize=0 read exactly 128 bytes and observed exit 4 after
3.028 seconds with no remaining bytes or diagnostic. The fixture now uses that
unbuffered read; the production deadline and expected outcome were not changed.
The repaired five-test run passed. Initial results remain separately retained.

File-wait probes inject a 6.5-second delay at the ordinary-file observation
boundary. They do not stall a Windows driver or qualify arbitrary kernel stalls.
Output probes use actual anonymous-pipe backpressure and disposable fake stores.
These working results precede the source-bound clean reproduction.
