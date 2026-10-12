# Review wording correction

The initial review said "output-before-validation behavior". That was a wording
error: the contract and code validate API arguments/capacity before publishing
output, and the fixtures assert unchanged output on errors. The review now says
"output preservation on API/capacity failures". Its exact previous bytes remain
in development-diagnostics/review-before-wording-correction.md and Git history.
No native source, expected outcome, result, authority or qualification scope changed.
