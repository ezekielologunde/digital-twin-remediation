# Final-verification race development experiment

5 October 2026. Plan written before execution. This is a controlled counterexample test, not a novel algorithm or confirmatory study.

Question: Can every final recorded dependency check succeed while a subsequent restart fails because a dependency changes during or after that collection?

Six fresh isolated instances: two synthetic account blocks, each with no additional fault, a Redis stop immediately after its successful final check but before the remaining checks, and a Redis stop after all final checks. Order shuffled with seed 20261011. Synthetic identities are not stochastic workload replicates.

The during-collection hook synchronously stops Redis and confirms it stopped before allowing MongoDB and Post RPC checks to proceed. This deliberately constructed ordering establishes possibility, not the frequency of naturally occurring concurrent failures. The after-collection hook stops Redis after all checks complete and before the approval is sealed and the action starts. Both mechanisms leave the recorded Redis result unchanged. Approval uses only the three recorded functional results, without fault labels or container-state oracle information.

Each probe records its own monotonic start and completion. Fault-command start, confirmed-stop boundary, collector start/end and action decision are also recorded. The decision is sealed before target-only docker start. All actions execute irrespective of approval. The contract remains exact content/creator verification in the last two scheduled reads within eight seconds, with no observed creator mismatch.

Hypotheses: The controls pass all checks and recover. Both injected placements can pass all checks yet fail the recovery contract. If a later probe fails, record that result rather than assuming the intended counterexample occurred. Unexpected initialization or cleanup failures halt the batch and remain retained. No results are replaced.

Audit raw command order, per-probe timing, prediction hash and evidence-only decision, outcome recomputation, target-only dependency states, fresh volumes and scoped cleanup. Report each trial, observed incorrect approvals, and per-probe age at action. No significance tests, probability-of-race estimates, safe evidence-age cutoff or new defense claims.

Boundaries: Fixed known Redis failure and fixed order, one benchmark, peer-container probes, short outcome horizon, limited account blocks, no fault during the restart itself. All dependencies are healthy initially, so this does not demonstrate that they were never simultaneously healthy. It tests whether past successful checks justify the later action. Passing this experiment would motivate a stronger guard baseline with fresh state or event invalidation, which itself would still require testing for observation-to-action gaps. No locking, lease, fencing or atomic authorization mechanism is implemented here.
