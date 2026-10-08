# Retained exploratory findings

The first 203-case exploratory fixture suite passed. Expanding it to 231 cases
failed `maximum-steps`; the other 230 cases passed. Its request value was retained
by reference in the Python harness and later extended for the 65,536-byte fixture,
while its independently computed expectation still described the original value.
The resulting native payload matched the later supplied value, not that earlier
expectation. This was a fixture-lifetime error, not evidence of a mutable prepared
native definition. The original failing log/JSON are retained.

Case creation now deep-copies fixture inputs. The 231-case repair and clean source
57177457 passed without a native-code change. Review then added explicit catalog
entries for smaller collection limits and 12 boundary cases. Final clean source
8ec0404f passed all 243 cases. Expectations were not changed to accept the earlier
mutation: the harness now sends the value for which its expectation was computed.

An initial specctl invocation through the system Python executable lacked spec
dependencies. The existing project virtual environment already contained exact
PyYAML/jsonschema pins and was used instead; no software was installed. This
coordinator-environment error is separate from native compilation and service
restrictions. No hosted-service refusal occurred during this component's tools.
