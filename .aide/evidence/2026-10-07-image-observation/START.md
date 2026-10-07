# DE-W024 first map-observation slice

Base is the W023 review checkpoint c20b4d7 (full revision recorded by the handoff).
The explicit local cross-unit grant applies; owner acceptance remains separate.
The DE-W024 preparation context was generated and verified at this checkpoint.

First implement and test one private bounded map-observation function over an
immutable captured byte prefix with explicit source geometry. It integrates the
qualified C90 readers; it performs no file I/O and makes no source-stability
claim. File capture, shared command admission and actual frontend parity follow
within W024. Product image commands remain unavailable until those parts qualify.
Expected report behavior is specified in DE-102 before evaluating this code.
