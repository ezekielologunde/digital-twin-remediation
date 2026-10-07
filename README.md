# Remediation evidence validity in microservices

**When Successful Checks Outlive Their Evidence: A Reproducible Case Study of Remediation Approval in Microservices**

A research project investigating when evidence used to approve a recovery action stops being reliable. Built with Python and a Docker-based DeathStarBench social-network testbed. Maintained by [Ezekiel Ologunde](https://github.com/ezekielologunde).

**Status:** public research artifact and manuscript draft, not a peer-reviewed publication. The study reports 50 action trials across five successive development stages. Analysis replay is verified; the manuscript PDF build and visual review remain unverified. This project is independent of coursework and doctoral Praxis.

## Event-retention study completed

**24 new trials completed**, under a plan committed before collection. [Results and replay instructions](pilot/retention-runs/323a0268545b4b909930322a933722ab/Results.md). Verified history omission caused six incorrect event-policy approvals in six stopped-Redis-plus-churn cases. Fresh Running-state and functional checks abstained. All 12 healthy controls recovered. No exclusions or replacement trials; 312 unique trial volumes and cleanup were verified. This is a controlled known boundary, not a general effectiveness or safety claim.

Latest paper: [ACM v0.4 source](overleaf/acm-v0.4.tex), [Overleaf ZIP](downloads/Overleaf-case-study-v0.4-acm.zip). Eight tables and two vector diagrams. PDF compilation remains unverified. Earlier v0.2 and v0.3 sources remain versioned. Rebuild v0.4 with `python publication/build_acm_v0_4.py` after replaying the archived analyses.

## Previous working paper (v0.3)

[ACM manuscript v0.3](overleaf/acm-v0.3.tex) adds two vector diagrams, seven formatted tables, and a post-hoc endpoint sensitivity analysis of the same 50 trials. [Overleaf source ZIP](downloads/Overleaf-case-study-v0.3-acm.zip). Author: **Ezekiel Ologunde, Independent Researcher**. No institutional affiliation. Corresponding email and journal choice remain pending. ACM is the intended publication route, not an acceptance claim. PDF compilation remains unverified because of a compiler environment error.

At 4, 6, and 8 seconds, all original outcome labels persist across one, two, and three required final reads. Two-second results include changed labels and insufficient observations. These are dependent reanalyses, not new experiments. Reproduce using `python pilot/analyze_sensitivity.py` then `python publication/build_acm_manuscript.py`. The original v0.2 manifest and manuscript are preserved unchanged; the new source uses a separate versioned filename.

The v0.3 draft predates the now-completed 24-trial event-retention experiment; see the v0.4 results above. Future code, eligible data, results and author-permitted final manuscripts will be versioned in this repository. Original work remains unlicensed.

## Research question

When dependencies change between observation and remediation, how do direct dependency checks, evidence refresh timing, lifecycle-event observations, and late functional rechecking affect approval errors?

The original digital-twin direction motivated the work. The implemented contribution is a bounded, reproducible case study of evidence validity, not a calibrated digital twin, a new race condition, or a proven autonomous defense.

## Findings

The final comparison used eight shared action outcomes. Each policy evaluated the same trials; its rows are not independent experiments.

| Policy | Approvals | Incorrect approvals | Recoverable cases rejected |
| --- | ---: | ---: | ---: |
| Initial final checks | 8 | 4 | 0 |
| Fresh running-state checks | 6 | 2 | 0 |
| Available lifecycle events | 4 | 0 | 0 |
| Events withheld for ten seconds | 8 | 4 | 0 |
| Events silently dropped | 8 | 4 | 0 |
| Late functional rechecking | 4 | 0 | 0 |

Available events and late functional rechecking tied. This cohort does **not** establish superiority of the event method. Earlier stages examine missing direct dependencies, early-stop probe collection, evidence timing, and changes during or after final verification.

## Start here

- [Manuscript source](overleaf/main.tex) and [Overleaf upload ZIP](downloads/Overleaf-case-study-v0.2.zip).
- [Data guide](DATA.md): study stages, exclusions, provenance, and interpretation.
- [Reproduction commands](REPLAY.txt), or run the verification script below.
- [Literature and claims audit](publication/Literature%20and%20claims%20audit.md).
- [Experiment index](pilot/Experiments%20index.md) includes historical context; only the batches described in DATA.md are distributed here.
- [Release notes](RELEASE.md) and [third-party notices](NOTICE.md).

## Reproduce without Docker

Requires Python 3.11 or newer. The analysis and unit tests use the standard library. From the repository root:

```sh
python scripts/verify_release.py
```

This checks every original artifact against MANIFEST.json, runs 40 unit tests, and replays the five analyses plus manuscript generation in a temporary copy. It verifies byte-for-byte output equality and leaves the committed evidence untouched. It does not start containers or contact external systems.

An optional GitHub Actions definition is included at `docs/verify-workflow.yml.example`. It is not enabled because the publishing token lacks workflow scope.

## Repository layout

| Path | Contents |
| --- | --- |
| `pilot/*-runs/` | Selected raw trial ledgers, plans, frozen inputs and code, outcomes, analyses, and excluded attempts |
| `pilot/*.py` | Analysis, policy tests, and historical experiment runners |
| `overleaf/` | Standalone manuscript and its generation template |
| `publication/` | Table generator, claims audit, provenance, historical packaging records |
| `MANIFEST.json` | SHA-256 hashes of the original evidence-package payload |
| `downloads/` | Versioned Overleaf source ZIP |
| `scripts/verify_release.py` | Non-destructive offline reproducibility check |

## Live experiments

Historical runners are included for methodological transparency. They are not a portable one-command deployment: original host bind paths must be adapted and pinned images/runtime assets obtained separately. Frozen configuration records document the environment. No Docker images, database volumes, or running services are redistributed. The verification script above is the supported offline entry point.

Experiments used synthetic accounts/content and isolated, disposable testbed instances. The measured action was starting one verified target container. Outcomes measure availability and exact-content recovery, not containment, authorization, or production safety. Approval policies were shadow evaluations; actions still executed, so these results do not measure a deployed gate's effectiveness.

## Limits and research status

This is a small, deliberately constructed case study with successive development stages. Do not pool the 50 trials as identically distributed observations or treat policy views as independent samples. Fault schedules and event-delivery transformations were controlled. No general accuracy, statistical significance, new mechanism, or production-safety claim is supported. Source/image correspondence is not independently verified.

Author declarations and final manuscript review remain open. GitHub availability does not constitute journal acceptance. See publication/README.txt for the historical author-review checklist. AI-assisted research/code/manuscript preparation is disclosed in the manuscript; all claims require human review.

## Reuse

The original work is intentionally unlicensed pending the owner's decision. Public visibility is not a grant of an open-source or data reuse license. Third-party material retains its own license; see NOTICE.md. Downloaded research papers and unrelated school materials are not included.
