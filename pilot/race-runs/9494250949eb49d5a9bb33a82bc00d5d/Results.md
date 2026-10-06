# Changes during and after final verification

Development experiment, 5 October 2026. Six fresh instances across two account blocks. The verifier approves only when all three recorded final checks succeed. Fault placement is not a policy input.

| Placement of Redis stop | Trials | Approvals | Incorrect approvals | Recovery contracts met |
|---|---:|---:|---:|---:|
| none | 2 | 2 | 0 | 2 |
| during_final | 2 | 2 | 2 | 0 |
| after_final | 2 | 2 | 2 | 0 |

| Block | Condition | All checks passed | Recovery contract | Redis check age at action (s) | Whole collection end age (s) |
|---|---|---|---|---:|---:|
| 901 | none | True | True | 0.601 | 0.007 |
| 902 | during_final | True | False | 1.621 | 0.009 |
| 901 | during_final | True | False | 1.526 | 0.009 |
| 902 | after_final | True | False | 1.632 | 0.994 |
| 901 | after_final | True | False | 1.677 | 1.056 |
| 902 | none | True | True | 0.601 | 0.007 |

During-collection injection is a deliberately blocking hook: Redis is stopped after its successful check and before MongoDB is checked. After-collection injection occurs once all checks have completed. These are controlled counterexamples, not samples of natural concurrent failures.

A small age measured from completion of the whole collection can conceal an older individual Redis result. Individual probe completion ages are recorded in analysis.json. All dependencies were healthy initially; this study does not show they were never simultaneously healthy.

The recorded approval is sealed before target-only restart. The injector knows the fault; the verifier receives only check results. An observer using additional fresh container state might abstain, but that stronger policy is not evaluated here. Neither a locking/lease defense nor a deployed gate is implemented.

Integrity audit covers raw event order, per-probe timestamps, source/configuration/ledger hashes, sealed evidence, independently recomputed outcomes, action scope, independent volumes and cleanup return codes. Live resource absence is verified separately.

Deterministic fault scheduling with a blocking hook, two synthetic account blocks, known Redis stop, fixed order. Not natural race incidence, a novel algorithm, a coherence proof, or a test of concurrency control.
