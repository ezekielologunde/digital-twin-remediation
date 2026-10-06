# Lifecycle-event invalidation results

Development study, 5 October 2026. Eight fresh trials, one outcome per instance shared by five shadow policies. Actual Docker lifecycle records were queried; ten-second withholding and silent dropping are simulated channel transformations.

| Policy | Approvals | Incorrect approvals | Correct approvals | Recoverable cases rejected |
|---|---:|---:|---:|---:|
| final_checks | 8 | 4 | 4 | 0 |
| fresh_running_state | 6 | 2 | 4 | 0 |
| events_available | 4 | 0 | 4 | 0 |
| events_delayed | 8 | 4 | 4 | 0 |
| events_silently_dropped | 8 | 4 | 4 | 0 |

| Block | Condition | Matched lifecycle changes | Recovery contract | Query duration (ms) |
|---|---|---|---|---:|
| 1001 | unrelated_stop | none | True | 207.8 |
| 1001 | storage_suspend | kill | False | 190.9 |
| 1001 | redis_stop | kill, stop, die | False | 207.2 |
| 1002 | none | none | True | 202.8 |
| 1002 | unrelated_stop | none | True | 204.2 |
| 1002 | storage_suspend | kill | False | 233.2 |
| 1001 | none | none | True | 241.8 |
| 1002 | redis_stop | kill, stop, die | False | 268.3 |

Query time is measured common overhead, not a policy-specific latency comparison. Docker history retains only the last 256 records; absence of a matching event does not certify completeness. Silent loss is not detectable merely from an empty event set. All changes precede observation; a later change could invalidate these decisions too.

An earlier two-arm batch was excluded because a list-name collision let subsequent ledger entries mutate the saved event inputs. Its raw files and deviation report are retained. This corrected batch verifies exact equality between sealed and final event inputs, replays decisions from the raw daemon-query receipts and audits prediction-before-action ordering.

Actual daemon history, simulated channel delay/drop, shared outcomes and interventions, no reliable live event stream or natural loss estimate. Known post-verification faults, two account blocks, no deployed gate or held-out evaluation.
