"""Post-hoc endpoint sensitivity using unchanged raw records, without Docker."""
import hashlib
import json
from pathlib import Path
from probe import classify_read

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    'direct': 'direct-runs/3049d39ca8b942858f518d4b5b2317b1',
    'sequential': 'sequential-runs/5f71ebb803bd4d939e978b6e80eeecf5',
    'temporal': 'temporal-runs/294bab8ce4274cb7b50c52b48b59c78b',
    'race': 'race-runs/9494250949eb49d5a9bb33a82bc00d5d',
    'aligned_event': 'aligned-event-runs/fc54dc7bbf804c07b54d357033a60c70',
}

def endpoint(observations, horizon, required):
    observed = [o for o in observations if o['elapsed_s'] <= horizon]
    if len(observed) < required:
        return None
    return (all(o['classification'] == 'verified_readback' for o in observed[-required:])
            and not any(o['classification'] == 'creator_mismatch' for o in observed))

def analyze():
    hashes, stages = {}, {}
    def read(path):
        raw = path.read_bytes()
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
        return raw
    for stage, relative in STAGES.items():
        batch = ROOT / 'pilot' / relative
        rows = json.loads(read(batch / 'summary.json'))
        folders = {json.loads(p.read_text())['project']: p.parent
                   for p in batch.glob('*/summary.json')}
        for row in rows:
            assert row['status'] == 'COMPLETE'
            folder = folders[row['project']]
            assert json.loads(read(folder / 'summary.json')) == row
            ledger = read(folder / 'ledger.jsonl')
            assert hashlib.sha256(ledger).hexdigest() == row['ledger_sha256']
            raw_scenario = read(folder / 'scenario.json')
            assert hashlib.sha256(raw_scenario).hexdigest() == row['scenario_sha256']
            scenario = json.loads(raw_scenario)
            events = [json.loads(line) for line in ledger.decode().splitlines()]
            obs = row['outcome_observations']
            recorded = [e for e in events if e['kind'] == 'outcome']
            reads = [e for e in events if e['kind'] == 'http' and e['phase'] == 'outcome_read']
            assert len(obs) == len(recorded) == len(reads)
            assert [o['elapsed_s'] for o in obs] == sorted(o['elapsed_s'] for o in obs)
            for o, event, response in zip(obs, recorded, reads):
                assert all(o[k] == event[k] for k in ('elapsed_s', 'classification'))
                assert o['classification'] == classify_read(response['status'], response['body'],
                                                            scenario['markers'][-1], scenario['user_id'])
            original = (len(obs) >= 2 and all(o['classification'] == 'verified_readback'
                        and o['elapsed_s'] <= 8 for o in obs[-2:])
                        and not any(o['classification'] == 'creator_mismatch' for o in obs))
            assert original == row['contract_met']
        cells = []
        for horizon in (2, 4, 6, 8):
            for required in (1, 2, 3):
                labels = [endpoint(r['outcome_observations'], horizon, required) for r in rows]
                cells.append({'horizon_s': horizon, 'consecutive_final_reads': required,
                              'recovered': sum(x is True for x in labels),
                              'failed': sum(x is False for x in labels),
                              'insufficient_observations': sum(x is None for x in labels),
                              'changed_labels': sum(x is not None and x != r['contract_met']
                                                    for x, r in zip(labels, rows))})
        stages[stage] = {'trials': len(rows), 'original_recovered': sum(r['contract_met'] for r in rows),
                         'cells': cells,
                         'trial_labels': [{'project': r['project'],
                             'labels': {f'{h}s_{k}reads': endpoint(r['outcome_observations'], h, k)
                                        for h in (2, 4, 6, 8) for k in (1, 2, 3)}} for r in rows]}
    result = {'analysis': 'post-hoc endpoint sensitivity', 'date': '2026-10-06',
              'raw_classifications_recomputed': True, 'stages': stages, 'input_sha256': hashes,
              'limits': 'Prefix analysis of existing observations, not new trials or new polling schedules. '
                        'Null means insufficient observations. No observations beyond eight seconds. '
                        'Different horizons can have different time since the last observed read. '
                        'Neither generalization nor a prespecified confirmatory test.'}
    out = ROOT / 'publication' / 'sensitivity'
    out.mkdir(exist_ok=True)
    (out / 'analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: {x: v[x] for x in ('trials', 'original_recovered', 'cells')}
                      for k, v in stages.items()}, indent=2))

if __name__ == '__main__':
    analyze()
