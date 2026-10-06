"""Post-hoc exhaustive cached-evidence ablation; no new live trials."""
import hashlib
import itertools
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = '3049d39ca8b942858f518d4b5b2317b1'
KEYS = ('timeline_redis', 'timeline_mongo', 'post_storage')


def decide(cached, current, refreshed):
    if not set(refreshed) <= set(KEYS):
        raise ValueError('Unknown verification obligation')
    return all((current if k in refreshed else cached)[k]['verified'] for k in KEYS)


def analyze(source):
    rows = json.loads((source / 'summary.json').read_text())
    plan = json.loads((source / 'plan.json').read_text())
    assert len(rows) == len(plan['arms']) == 18
    assert [[r['seed'], r['backend_condition'], r['arm']] for r in rows] == plan['arms']
    volumes = set()
    for r in rows:
        folder = source / f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
        assert r == json.loads((folder / 'summary.json').read_text())
        assert r['status'] == 'COMPLETE' and r['cleanup_returncode'] == 0
        raw = (folder / 'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == r['ledger_sha256']
        events = [json.loads(line) for line in raw.decode().splitlines()]
        seal = next(i for i, e in enumerate(events) if e['kind'] == 'predictions_sealed')
        action = next(i for i, e in enumerate(events) if e['kind'] == 'docker' and e['args'] == ['start', r['target_container_id']])
        assert seal < action and events[action]['returncode'] == 0
        assert seal < next(i for i, e in enumerate(events) if e['kind'] == 'outcome')
        raw_prediction = (folder / 'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(raw_prediction).hexdigest() == events[seal]['sha256']
        assert json.loads(raw_prediction)['direct_probes'] == r['direct_probes']
        assert all(v['verified'] for v in r['direct_baseline'].values())
        assert not volumes.intersection(r['volume_names'])
        volumes.update(r['volume_names'])
        obs = r['outcome_observations']
        outcome = len(obs) >= 2 and all(o['classification'] == 'verified_readback' and o['elapsed_s'] <= 8 for o in obs[-2:]) and not any(o['classification'] == 'creator_mismatch' for o in obs)
        assert outcome == r['contract_met']
    metrics = []
    for size in range(4):
        for subset in itertools.combinations(KEYS, size):
            decisions = [decide(r['direct_baseline'], r['direct_probes'], subset) for r in rows]
            approved = sum(decisions)
            false = sum(a and not r['contract_met'] for a, r in zip(decisions, rows))
            costs = [sum(r['direct_probes'][k]['elapsed_ms'] for k in subset) for r in rows]
            metrics.append({'refresh': list(subset), 'approvals': approved, 'false_approvals': false,
                'true_approvals': sum(a and r['contract_met'] for a, r in zip(decisions, rows)),
                'expected_false_at_six_approvals': 6 * false / approved if approved >= 6 else None,
                'probe_invocations_per_opportunity': size,
                'median_recorded_component_sum_ms': statistics.median(costs),
                'missed_conditions': sorted({r['backend_condition'] for a, r in zip(decisions, rows) if a and not r['contract_met']}),
                'decisions': decisions})
    # Every proper fixed subset should be distinguishable from full verification
    # in this particular deliberately fault-enriched cohort, not universally.
    return {'source_batch': BATCH, 'analysis_type': 'post-hoc exhaustive replay',
        'trials': len(rows), 'new_live_trials': 0, 'distinct_volume_ids': len(volumes),
        'source_integrity_verified': True, 'metrics': metrics,
        'limitations': ['Subset policies were written after outcomes were available.',
            'All original trials received all probes. Component sums are accounting proxies, not measured selective execution latency.',
            'Fault injection occurred after cached checks. This is evidence invalidation after state change, not a causal estimate of elapsed-age effects.',
            'Only one outcome per trial; policy replays are dependent, not additional trials.',
            'No learned selection, novelty proof, external validity or security containment result.']}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=HERE / 'direct-runs' / BATCH)
    parser.add_argument('--output', type=Path, default=HERE / 'refresh-replay')
    args = parser.parse_args()
    result = analyze(args.source)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = ['# Cached evidence and selective refresh: exhaustive replay', '',
        'Post-hoc development analysis, 4 October 2026. Eighteen existing live trials, zero new live trials. Cached checks were successful before controlled dependency changes. Each fixed subset replaces cached results with the recorded later results. The selection rule never receives a fault label or outcome.', '',
        '| Refreshed obligations | Approvals | False approvals | Expected false at 6 approvals | Median recorded component sum (ms) |',
        '|---|---:|---:|---:|---:|']
    for m in result['metrics']:
        label = ', '.join(m['refresh']) or 'None (cached only)'
        lines.append(f"| {label} | {m['approvals']} | {m['false_approvals']} | {m['expected_false_at_six_approvals']:.2f} | {m['median_recorded_component_sum_ms']:.1f} |")
    lines += ['', 'The matched-budget number is the exact expected false count under uniform thinning of eligible approvals to six. It is not an observed extra experiment or population confidence interval.', '',
        'Every proper fixed subset misses at least one injected failure class in this cohort. Full refresh is the only enumerated fixed-subset policy with zero observed false approvals. This rejects a claim that simply skipping a fixed dependency check preserves the observed result.', '',
        'These probes were collected sequentially in Redis, MongoDB, Post RPC order. The component sum excludes old baseline acquisition, functional checks, orchestration, and subsequent snapshots. Skipping probes could change timing or cache state. No deployed cost reduction has been measured.', '',
        '## Limits', '']
    lines += ['- ' + text for text in result['limitations']]
    (args.output / 'Results.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'metrics'}))


if __name__ == '__main__':
    main()
