# Working-tree diagnostics

The initial GCC strict syntax command rejected a width comparison that was
always false on this host. Initialization now uses the existing checked
de_u64-to-size conversion, retaining width refusal on narrower hosts. The initial
native probe build failed because its array builder called an API that does not
exist. The probe now constructs arrays through the existing value interface.
The subsequent focused run passed. These logs are development diagnostics;
the clean revision-bound campaign separately establishes qualification.
