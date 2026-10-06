# Literature and claims audit

5 October 2026. Focused review, not a systematic search or proof of priority. Preprints are identified as such; title-page journal styling is not acceptance evidence.

| Source | Evidence reviewed | Established overlap | Consequence for our claim |
|---|---|---|---|
| [GuardedAct, 2026 preprint](https://arxiv.org/abs/2609.11264) | Local full text and current arXiv metadata; limitations discuss graph completeness and runtime nondeterminism | Sandbox-first remediation and execution gating already exist, including in DeathStarBench | We do not claim gated remediation or the benchmark choice as new. No head-to-head replication has been run. |
| [HAVE, 2026 preprint](https://arxiv.org/abs/2606.06968) | Local full text and current arXiv metadata, which says submitted for possible IEEE publication | Active host verification updates security-twin risk estimates | Active verification is not new; our endpoint is availability, not compromise probability. |
| [ConfExp, 2025](https://doi.org/10.1007/s10922-024-09886-w) | Publisher full text, especially sections 2.2 and 3 | Sequential diagnostic tests; assumptions include persistent faults and leave unpredictable distributed delays outside scope | This explicit boundary motivates temporal experiments. It does not prove that other work lacks them. |
| [AdaMC, 2025](https://real.mtak.hu/225526/) | Repository abstract only; full text restricted | Adaptive monitoring frequency and resource overhead | Do not claim adaptive monitoring cost as new; detailed methodological comparison remains incomplete. |
| [Signalling Health, 2025 preprint](https://arxiv.org/abs/2507.02158) | Local full text and current metadata | Signal-based monitoring compared with polling in SockShop | Event notification is established. Our bounded history queries are not that streaming system. |
| [Gray Failure, 2017](https://www.microsoft.com/en-us/research/publication/gray-failure-achilles-heel-cloud-scale-systems/) | Local paper and publisher/author metadata | Differential observability across observers | Running flags and peer probes can disagree with application behavior; that general insight is not ours. |
| [CWE-367](https://cwe.mitre.org/data/definitions/367.html) | Official definition and mitigation discussion | Changes between check and use are a known failure pattern | Our deterministic examples are not a newly discovered vulnerability class. |
| [Docker event reference](https://docs.docker.com/reference/cli/docker/system/events/) | Official command, formatting and retention documentation | Lifecycle events and a bounded 256-event history | Actual event visibility can be tested, but no-event results do not establish complete observation. |

The candidate empirical contribution is the documented combination of action-specific obligations, per-obligation timestamps, lifecycle visibility and independently measured restart outcomes, with replayable raw evidence and disclosed exclusions. Its significance and novelty remain matters for scholarly assessment. The current small development corpus does not justify claiming a universal guarantee or a superior new algorithm.

The initial event diagnostic gave its event guard newer evidence than the functional baseline. The subsequent aligned comparison explicitly adds post-fault functional checks. This correction must appear in the manuscript and artifact history; it must not be disguised as a preplanned held-out test. Even in the aligned comparison, event collection and late probes are sequential and share the same outcome, so policy-specific latency advantages are not established.

Prohibited claims: production-safe, security containment validated, digital twin calibrated, statistically significant improvement, first-ever race detection, event guard superior to all fresh functional checking, naturally measured event-loss frequency, journal accepted, or publicly available dataset before an actual deposit exists.
