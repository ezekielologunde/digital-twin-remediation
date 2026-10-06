# Sequential verification development experiment

Written before the new batch, after the exhaustive cached-evidence replay. This is a development protocol, not a public preregistration or confirmatory study.

Question: Does stopping verification at the first failed obligation reduce the measured dependency-check block duration while preserving the observed approval validity of complete checking on the existing controlled fault families?

Hypothesis: Sequential checking will make the same decisions as exhaustive checking under stable injected conditions. It should save probe invocations for Redis and MongoDB failures, but not for post-storage failures, which are checked last. Timing savings are uncertain and must be measured. This is a conventional short-circuit baseline, not a novel algorithm.

Design: Twelve fresh isolated trials. One synthetic account block, six existing conditions, two modes. Conditions are healthy, unrelated media stopped, post-storage process suspended, timeline Redis stopped, timeline MongoDB stopped with long reads, and the same MongoDB fault with short reads. Each condition receives both modes in independently reset instances. The global order is shuffled with seed 20261009. No fault labels enter the decision function.

Modes: Full checking always runs Redis, MongoDB and Post RPC in that order. Early stopping uses that same order and abstains on the first failed check. Unexecuted checks are explicitly unknown, not failed measurements. Every approval requires all three verified. Both modes use the same healthy initialization, baseline checks, alternate-route check and target-only start action. Actions run regardless of the recorded decision to obtain recovery outcomes.

Primary descriptive outcomes: false approvals and true approvals against the existing eight-second content-and-creator recovery contract; number of executed probes; actual elapsed wall time around the direct collector, including its logging. For each condition report both raw times and their difference. Report aggregate medians but no p-values, confidence intervals or population speedup claims. Do not count shared old replay policies as additional trials.

Reject implementation if a skipped probe executes, approval occurs with any unverified obligation, predictions are not sealed before action, the target-only scope check fails, or temporary resources are not removed. Preserve failed or incomplete attempts and stop the batch for inspection. Do not replace inconvenient results.

Limits: One observation per mode and condition, one fixed order, sequential environmental drift, Docker client overhead, cache warming by common setup, deliberately enriched known faults, eight-second outcome horizon, and peer-container probe vantage. No elapsed-age manipulation, nonstationary race evaluation, learning, security-containment test, source-to-image verification, unseen-fault generalization or journal-level novelty established.

Next decision rule: If both modes have identical observed validity and early stopping reduces calls as intended, retain it as a mandatory inexpensive baseline for any later adaptive method. If validity differs, inspect all raw evidence before interpreting timing. Evidence-age experiments need independently varied delays and state-change times; a cached-before-fault replay cannot isolate age itself.
