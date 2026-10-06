# Sequential verification results

Development study, 4 October 2026. Twelve fresh instances, six conditions and two modes. Approval requires all three checks; early stopping abstains at the first failed check. Unexecuted checks remain unknown.

| Mode | Trials | Approvals | False approvals | Executed checks | Median direct-check block (ms) |
|---|---:|---:|---:|---:|---:|
| full | 6 | 2 | 0 | 18 | 969.6 |
| early_stop | 6 | 2 | 0 | 14 | 721.5 |

| Condition | Full (ms) | Early stop (ms) | Full minus early stop (ms) | Same decision and outcome |
|---|---:|---:|---:|---|
| mongo_down_short | 939.8 | 553.3 | 386.6 | True |
| process_suspended | 1925.5 | 1929.0 | -3.5 | True |
| timeline_mongo_down | 999.4 | 587.0 | 412.4 | True |
| timeline_redis_down | 1031.2 | 261.4 | 769.8 | True |
| unrelated_down | 821.8 | 856.0 | -34.2 | True |
| up | 825.7 | 924.1 | -98.5 | True |

These are actual elapsed direct-collector durations including command logging. Both modes have common initialization and functional probing outside this interval. Durations exclude baseline acquisition, fault setup, subsequent snapshots and recovery. Each condition has only one trial per mode; account identity is held fixed and data volumes are independent. Timing differences can reflect machine load, Docker client overhead and other environmental variation. No significance, general speedup, production risk bound or security claim is made.

Actions executed even when the verifier abstained. Outcomes assess whether approval would have been correct, not the effectiveness of a deployed gate. The eight-second recovery contract is availability and content verification, not attack containment.

Integrity checks cover recorded plan order, source/configuration hashes, complete baseline checks, sealed predictions before action, actual calls and skipped checks, independently recomputed outcome labels, target-only state checks, unique volumes and cleanup return codes. Live resource absence is recorded separately.

One separately reset instance per mode and condition, descriptive timing only; known faults and fixed order. Not an adaptive method or causal population speedup estimate.
