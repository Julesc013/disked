# W033 Windows file-acquisition component

Work base: `655a7d91b0fda453b74a4ea30c03635c7fda59c4`.
Private adapter implementation and working-tree observations are retained here;
source-bound clean reproduction and final implementing-agent review follow.
The public `image.acquire` command remains unavailable. DE-W033 and all DiskEd
0.1.0 remain incomplete; owner acceptance and physical/release authority are separate.

The adapter binds ordinary source, parents, owned outputs, local host observation,
executable and provider generation. Source/code handles and exclusive effect
handles coordinate normal file sharing. CREATE_NEW refuses competing owners;
partial outputs are retained. Bounded raw copying, canonical LF-framed maps,
explicit substitution, per-file flush/readback and matching-generation resume
use the provider-independent core. No device opens, elevation or installation.

Working checks cover independently generated image bytes/SHA-256, grants/aliases,
Unicode and chunk boundaries, real sharing/DACL refusal, CREATE_NEW races,
controlled API faults and observed child termination. See FINDINGS for retained
failures and the exact limits in DE-103. No snapshot, physical fencing, power-loss,
restore, other-host/platform or public-command qualification follows.
