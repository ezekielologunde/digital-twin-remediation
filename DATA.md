# Data and provenance

The outcome data were generated in controlled experiments on the openly available [DeathStarBench](https://github.com/delimitrou/DeathStarBench) social-network testbed. They are synthetic experimental records, not production traffic or human-subject records. Upstream source reference: `6ecb09706140f8730b5385c08f1386c654c3c526`. Source/image correspondence was not independently established.

## Primary manuscript cohorts

| Stage | Batch under pilot/ | Trials |
| --- | --- | ---: |
| Direct obligations | direct-runs/3049d39ca8b942858f518d4b5b2317b1 | 18 |
| Sequential collection | sequential-runs/5f71ebb803bd4d939e978b6e80eeecf5 | 12 |
| Refresh timing | temporal-runs/294bab8ce4274cb7b50c52b48b59c78b | 6 |
| Verification race | race-runs/9494250949eb49d5a9bb33a82bc00d5d | 6 |
| Aligned event comparison | aligned-event-runs/fc54dc7bbf804c07b54d357033a60c70 | 8 |

`plan.json` records the scenario plan; `summary.json` records completed trial summaries; per-trial `ledger.jsonl` records ordered observations, predictions, actions, outcomes and cleanup. Frozen prediction inputs and hashes support before-action ordering checks. `analysis.json` and `Results.md` are derived outputs. The analyzers validate hashes and stage-specific consistency conditions before reporting metrics.

A successful outcome requires the final two scheduled reads within the eight-second window to return the expected text and creator without a content mismatch. The code and raw trial records provide the exact stage-specific details.

## Development and exclusions

- `event-runs/0561985519f64e5999746c0006960374`: prior valid diagnostic, not part of the five-stage primary table set.
- `event-runs/7825aa3b0a7f453cbbb20201a8e43532`: excluded attempt with a mutable event-input collision. Retained with deviation records; not scored as valid evidence.
- `direct-runs/b7f6534f0418437094f9a0e4052935a6`: excluded attempt where Compose could start an additional dependency. Retained with deviation records.

Older development cohorts referenced in historical notes are not included in this curated release. RCAEval and BATADAL were investigated earlier but were not the outcome data for this manuscript and are not redistributed here.

## Integrity and privacy

MANIFEST.json preserves the original evidence ZIP's payload hashes. Raw records remain unchanged, including synthetic identifiers, container/network identifiers, and historical local filesystem paths. The documented `local-synthetic-account` password is a fixture, not an external account credential. A pre-publication scan found no GitHub token, AWS access key, private key, or JWT patterns; this pattern scan is not a guarantee against every possible sensitive string.

Copyrighted downloaded literature, private school documents, Docker volumes, and personal account credentials are excluded. DeathStarBench source excerpts retain the upstream Apache 2.0 license in `licenses/DeathStarBench-LICENSE`.

The five cohorts contain different fault mixes and repeated synthetic account blocks. No pooled inference, independent-policy sample count, confidence interval, or significance claim should be inferred from their combined size.
