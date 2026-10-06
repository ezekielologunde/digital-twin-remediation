# Lifecycle-event invalidation development experiment

5 October 2026. Plan and policy frozen before execution; analysis may be written during the batch. Not a public preregistration or held-out confirmatory evaluation.

Question: Does actual observed lifecycle evidence invalidate a now-incorrect approval, and how do delayed or silently dropped event delivery affect that benefit?

Eight fresh instances: two synthetic account blocks crossed with no new fault, unrelated media container stopped, timeline Redis stopped, and post-storage PID 1 suspended by SIGSTOP. All additional faults occur after successful final functional verification and before authorization. The suspended-process manipulation checks /proc/1/status, but that oracle does not enter any policy. Actions still execute to obtain labels regardless of the shadow decisions.

Baselines: final checks only; final checks plus freshly observed dependency container Running flags; and final checks plus lifecycle-event invalidation. Additional shadow channels hold the actual retrieved records for ten seconds or silently drop them all. Delayed/dropped channels are controlled delivery simulations, not measured network transport behavior. Policies receive no condition label or outcome. Event filtering uses the three dependency container IDs and a prespecified conservative set of lifecycle transitions. An unrelated container event must not invalidate approval.

Actual Docker event history is queried before final checks to establish a daemon-event cursor, and after the fault to obtain new records. Query timestamps and raw output are retained. Docker returns only the last 256 events; history retrieval is not a reliable streaming implementation or proof of event completeness. No-event observations may conceal missing events. This experiment intentionally does not add an oracle that tells the verifier a silent drop occurred. History-query and fresh-inspection time are common interventions, not separately randomized policy costs.

Hypotheses: Available relevant events may catch both stopped Redis and signalled post storage; the Running flag may catch only the stopped container. Delayed or silently missing evidence may preserve incorrect approvals. Both healthy and unrelated-change controls should remain eligible and recover. If Docker does not report a required event, record the miss, do not substitute the known injected fault as an event.

Outcomes: incorrect approvals, approvals, correct approvals, rejected opportunities that would have recovered, raw query duration and per-probe age. The recovery contract remains the last two scheduled reads within eight seconds verifying exact known content/creator, without observed creator mismatch. Report each cell; two account IDs are not diverse stochastic workloads. No p-values, general safety guarantees, natural event-loss probabilities or new algorithm claims.

Audit: sealed inputs and decisions before target-only action; raw event actions/IDs/cursor; delivery deadline relative to decision; independently recomputed policy outputs and recovery labels; fault state after action; unique volumes and verified cleanup. Failed attempts remain, and stop the batch. Event-unreported application faults, event-buffer overflow, changes after observation, target-specific networking and actual gate deployment remain outside scope.
