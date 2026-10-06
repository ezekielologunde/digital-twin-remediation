# Direct dependency verification results

Development experiment, 4 October 2026. Eighteen fresh start-action trials across three account-ID blocks and six conditions. Rules, source evidence and analysis were frozen before this batch, after prior diagnostics. All three policies share outcomes and the same probing interventions.

| Block | Additional condition | Alternate route | Redis | MongoDB | Post RPC | Recovery contract |
|---|---|---|---|---|---|---|
| 501 | mongo_down_short | True | True | False | True | False |
| 503 | unrelated_down | True | True | True | True | True |
| 502 | mongo_down_short | True | True | False | True | False |
| 502 | unrelated_down | True | True | True | True | True |
| 502 | process_suspended | False | True | True | False | False |
| 503 | mongo_down_short | True | True | False | True | False |
| 501 | up | True | True | True | True | True |
| 502 | up | True | True | True | True | True |
| 502 | timeline_mongo_down | True | True | False | True | False |
| 503 | up | True | True | True | True | True |
| 503 | timeline_redis_down | True | False | True | True | False |
| 503 | timeline_mongo_down | True | True | False | True | False |
| 501 | timeline_mongo_down | True | True | False | True | False |
| 501 | process_suspended | False | True | True | False | False |
| 501 | timeline_redis_down | True | False | True | True | False |
| 503 | process_suspended | False | True | True | False | False |
| 501 | unrelated_down | True | True | True | True | True |
| 502 | timeline_redis_down | True | False | True | True | False |

Every candidate starts the stopped timeline service. Up and unrelated_down are no-additional-fault and stopped-media conditions. Other conditions suspend storage PID 1, stop timeline Redis, stop timeline MongoDB with read range 0..100, or stop MongoDB with short read range 0..3. Each baseline has three verified posts. Recovery requires the last two scheduled target reads within eight seconds to verify content and creator, with no observed creator mismatch.

| Policy | Eligible approvals | Incorrect approvals | Expected incorrect at six approvals | Fixed-ranked subset incorrect |
|---|---|---|---|---|
| alternate_route | 15 / 18 | 9 | 3.6 | 3 |
| alternate_plus_redis | 12 / 18 | 6 | 3.0 | 2 |
| direct_dependencies | 6 / 18 | 0 | 0.0 | 0 |

The equal-coverage budget is six of eighteen opportunities (33.3 percent), not the 50 percent budget of the previous twelve-trial cohort. Uniform thinning and its exact error-count distribution are conditional on this cohort. Fixed-ranked subsets are secondary. Policies with fewer than six eligible approvals are infeasible; none is forced to approve. Differences across cohorts cannot be interpreted as controlled effect sizes.

The alternate-route policy verifies a known post through the follower home timeline. Its Redis extension additionally checks a known post ID in the target timeline Redis sorted set. The direct policy requires that Redis record, a MongoDB timeline record containing the known post ID, and a successful direct ReadPosts RPC returning the exact ID, content and author. Unverified results cause abstention. These are manually specified baselines, not an automatic dependency-discovery algorithm.

Startup matters: the pinned UserTimelineService source retries MongoDB index creation before serving requests. A short cached read therefore does not by itself justify dropping the MongoDB obligation for a start action. Startup source hash was checked against the pinned repository tree, but source-to-binary correspondence remains unverified. The MongoDB read probe is not a test of index-write permissions or a full simulation of startup.

Probes originate from existing peer containers on the project network, not the stopped target namespace. They read existing synthetic records and may warm caches or affect connections. Every trial receives all probes in the fixed order: alternate route, Redis, MongoDB, post RPC. Therefore no probe-versus-no-probe effect is isolated. The action horizon begins after probing; per-probe elapsed times, including Docker client startup for direct checks, are saved in summary.json. Those times are not a production verifier-overhead estimate.

Ledger hashes, prediction seals, model snapshots, state manipulations, read ranges and fresh storage identifiers verified. Repeated account IDs are not diverse stochastic workloads. No collateral-safety result, staleness interaction, randomized missing-edge effect or statistically generalizable reliability claim follows. The previous setup failures adapting the Lua client are retained outside this experiment.

Research decision: compare any future proposed verifier against this stronger direct baseline. Further evaluation must include credential or configuration faults, target-specific network views, probe staleness, workload changes and independent fault selection. A zero-error cohort would not establish completeness of these obligations or novelty of manually adding checks.
