# Event-retention study results

Completed 6 October 2026. Plan and source were committed before the 24 research trials at `6bb078d`. Two engineering pilots are excluded. Six fresh account blocks per condition, with balanced query order. One action outcome per instance is shared across the four shadow policies.

| Condition | Trials | Initial checks | Event history | Running state | Functional recheck |
| --- | ---: | ---: | ---: | ---: | ---: |
| healthy_idle | 6 | 0/6 | 0/6 | 0/6 | 0/6 |
| healthy_churn | 6 | 0/6 | 0/6 | 0/6 | 0/6 |
| stop_idle | 6 | 6/6 | 0/0 | 0/0 | 0/0 |
| stop_churn | 6 | 6/6 | 6/6 | 0/0 | 0/0 |

Cells are incorrect approvals / all approvals. 0/0 means no approvals, not a defined zero conditional error rate. All 12 healthy cases recovered; no recoverable cases were rejected. All 12 stopped-Redis cases failed the bounded recovery contract. All six stop-plus-churn cases had a witnessed stop absent from the retained-history response. Stop-without-churn cases retained it. Both observation orders showed this pattern.

Audits verified sealed decisions before action, raw-response reclassification, raw event-history replay, frozen sources, balanced order and 312 distinct trial volumes. Live cleanup confirmed no trial containers, networks or volumes remained. All 216 prespecified 4/6/8-second and 1/2/3-read sensitivity combinations retained the original outcome labels.

This validates a deliberately constructed history-retention failure boundary on one Docker host. It does not estimate natural loss frequency, prove production safety or establish event-policy superiority. Churn changes elapsed time as well as buffer occupancy. Independent continuous witnessing and the persistent known fault support the bounded omission claim, not a general causal latency estimate. This study is separate from the earlier 50 development trials and is not pooled with them.

Replay: `python pilot/analyze_retention.py pilot/retention-runs/323a0268545b4b909930322a933722ab`. For the additional source/order/sensitivity audit: `python pilot/verify_retention_release.py pilot/retention-runs/323a0268545b4b909930322a933722ab`. Do not use `--live-cleanup` when replaying on an unrelated machine. The archived release-audit.json records cleanup verified on the execution host.
