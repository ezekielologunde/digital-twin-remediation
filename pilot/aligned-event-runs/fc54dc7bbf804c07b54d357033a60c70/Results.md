# Lifecycle-event invalidation results

Development study, 5 October 2026. Eight fresh trials, one outcome per instance shared by six shadow policies. Functional rechecking was also performed after the fault, following the event query. Actual Docker lifecycle records were queried; ten-second withholding and silent dropping are simulated channel transformations.

| Policy | Approvals | Incorrect approvals | Correct approvals | Recoverable cases rejected |
|---|---:|---:|---:|---:|
| final_checks | 8 | 4 | 4 | 0 |
| fresh_running_state | 6 | 2 | 4 | 0 |
| events_available | 4 | 0 | 4 | 0 |
| events_delayed | 8 | 4 | 4 | 0 |
| events_silently_dropped | 8 | 4 | 4 | 0 |
| late_functional_recheck | 4 | 0 | 4 | 0 |

| Block | Condition | Matched lifecycle changes | Recovery contract | Query duration (ms) |
|---|---|---|---|---:|
| 1102 | unrelated_stop | none | True | 215.5 |
| 1102 | redis_stop | kill, stop, die | False | 200.5 |
| 1101 | none | none | True | 201.3 |
| 1101 | storage_suspend | kill | False | 209.7 |
| 1101 | redis_stop | kill, stop, die | False | 239.1 |
| 1102 | none | none | True | 202.6 |
| 1101 | unrelated_stop | none | True | 202.2 |
| 1102 | storage_suspend | kill | False | 296.2 |

Query time is measured common overhead, not a policy-specific latency comparison. Docker history retains only the last 256 records; absence of a matching event does not certify completeness. Silent loss is not detectable merely from an empty event set. All changes precede observation; a later change could invalidate these decisions too.

The earlier eight-trial event-visibility batch lacked a post-fault functional-recheck baseline; it remains a development diagnostic and is not pooled here. An earlier two-arm batch was excluded because a list-name collision let subsequent ledger entries mutate the saved event inputs. Its raw files and deviation report are retained. This corrected batch verifies exact equality between sealed and final event inputs, replays decisions from the raw daemon-query receipts and audits prediction-before-action ordering.

Actual daemon history, simulated channel delay/drop, shared outcomes and interventions, no reliable live event stream or natural loss estimate. Known post-verification faults, two account blocks, no deployed gate or held-out evaluation.
