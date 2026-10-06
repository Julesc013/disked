# Initial findings

The first native build and real page-boundary probe passed. The first 1019-case
run found one fixture isolation defect: the later overflow case mutated the same
input dictionary previously stored for the huge-but-in-bounds budget case. The
case constructor now deep-copies each input; expected results were unchanged.
The failing run (passed=false) and corrected 1019-case receipt are retained.
No production-reader change was needed for that failure.

The corpus includes independently produced valid tables whose array bytes differ
while their CRCs match, proving comparison does not use CRC equality as identity.
GPT header validation, complete array coverage and entry consistency remain
separate. Profile budgets, missing source consistency, external differential
tools and historical target qualification are not turned into corruption claims.
