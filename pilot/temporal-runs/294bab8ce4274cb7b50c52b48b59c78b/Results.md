# Temporal evidence invalidation results

Development manipulation study, 4 October 2026. Six fresh instances, three placements of a Redis stop and two waiting periods. Each trial supplies one action outcome shared by three shadow evidence policies.

| Evidence policy | Approvals | Incorrect approvals | Correct approvals | Expected incorrect at two approvals |
|---|---:|---:|---:|---:|
| cached | 6 | 4 | 2 | 1.33 |
| refresh_before_wait | 4 | 2 | 2 | 1.00 |
| last_moment_refresh | 2 | 0 | 2 | 0.00 |

The last column is a secondary exploratory comparison: the exact expectation under uniform thinning to two approvals, conditional on these outcomes. It is not a new experiment, confidence interval, or risk guarantee.

| Fault placement | Assigned wait (s) | Actual wait (s) | Cached decision | Middle refresh | Final refresh | Recovery contract |
|---|---:|---:|---|---|---|---|
| before_refresh | 8 | 8.001 | approve | abstain | abstain | False |
| after_refresh | 4 | 4.001 | approve | approve | abstain | False |
| after_refresh | 8 | 8.000 | approve | approve | abstain | False |
| none | 4 | 4.000 | approve | approve | approve | True |
| none | 8 | 8.000 | approve | approve | approve | True |
| before_refresh | 4 | 4.001 | approve | abstain | abstain | False |

The assigned wait is measured from middle-collection completion to final-collection start, not to the action. Actual collection-end-to-action ages are in analysis.json. Earlier probes within each sequential collection are older than that group age.

Integrity checks cover source/configuration hashes, recorded arm order, command receipts, sealed predictions, fault/probe ordering, timing tolerance, independent outcome recomputation, target-only dependency state, fresh volume identities and cleanup return codes. Live absence is verified separately.

One trial per delay/placement cell. Shared probes and outcomes. Collection-end ages underestimate the age of earlier individual probes. No fault occurs after final verification; no atomicity or general reliability claim.

Interpretation: a controlled state change can invalidate previously successful verification. Detecting changes before the final recheck does not demonstrate protection against a later change. These known-fault examples do not estimate a time-to-expiry threshold or establish research novelty.
