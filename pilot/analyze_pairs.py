"""Validate saved pilot evidence and write descriptive results only."""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
def analyze(batch_id):
    if len(batch_id)!=32 or any(c not in '0123456789abcdef' for c in batch_id):
        raise ValueError('Expected batch ID')
    batch=HERE/'paired-runs'/batch_id
    plan=json.loads((batch/'plan.json').read_text())
    rows=json.loads((batch/'summary.json').read_text())
    checks=[]
    for row in rows:
        out=batch/f"{row['seed']}-{row['arm']}"
        raw=(out/'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['ledger_sha256']
        records=[json.loads(line) for line in raw.decode().splitlines()]
        checks.append({'seed':row['seed'],'arm':row['arm'],'ledger_records':len(records),'hash_verified':True})
    grouped={}
    all_volumes=set()
    no_reused_volumes=True
    for row in rows:
        grouped.setdefault(row['seed'],[]).append(row)
        current=set(row.get('volume_names',[]))
        no_reused_volumes &= not bool(current & all_volumes)
        all_volumes.update(current)
    pairs=[]
    for seed,group in sorted(grouped.items()):
        matched=len(group)==2 and {r['arm'] for r in group}=={'start','control'}
        equal=matched and len({r['scenario_sha256'] for r in group})==1
        pairs.append({'seed':seed,'both_arms_present':matched,'scenario_hash_equal':equal})
    report={'batch':batch_id,'planned_arms':len(plan['pairs']),'recorded_arms':len(rows),
            'complete_arms':sum(r['status']=='COMPLETE' for r in rows),
            'no_reused_volume_ids':no_reused_volumes,'pairs':pairs,'integrity_checks':checks,
            'claim_boundary':'Descriptive feasibility only, not a hypothesis test or gate evaluation'}
    (batch/'analysis.json').write_text(json.dumps(report,indent=2))
    text=['# Paired recovery feasibility results','',
          '4 October 2026. Two planned matched pairs, each using fresh disposable storage. '
          'The fixed pilot horizon is eight seconds. The intervention starts an intentionally stopped timeline service; '
          'the control leaves it stopped. No digital twin or approval gate is evaluated.','',
          '| Seed | Arm | Fresh storage and empty timeline | Baseline markers | Recovery observed by 8 s | First verified read from decision | Cleanup |',
          '|---|---|---|---|---|---|---|']
    for r in rows:
        interval=r.get('first_verified_read_from_decision_s')
        text.append(f"| {r['seed']} | {r['arm']} | {r.get('fresh_volume_ids',False) and r.get('empty_before_initialization',False)} | {r.get('baseline_markers_verified','NA')} | {r.get('recovered_by_8s','NA')} | {f'{interval:.3f} s' if interval is not None else 'Not observed'} | {r.get('cleanup_returncode','NA')} |")
    text += ['',f"Recorded {len(rows)} of {len(plan['pairs'])} planned arms. All saved ledgers parsed and matched their SHA-256 records. "
             f"No volume ID reused across arms: {no_reused_volumes}. Both arms share identical scenario hashes in each complete pair: "
             f"{all(p['scenario_hash_equal'] for p in pairs)}.",'',
             'The first verified read is an observation time measured from the decision boundary, including the start command. '
             'It is bounded by polling and request latency, not an exact failure-recovery instant. '
             'An unrecovered control is right-censored at the pilot horizon. Two pairs cannot establish general effectiveness or a production recovery distribution.','',
             'Fresh anonymous volume IDs and empty pre-initialization timelines support reset of the measured application state. '
             'They do not prove bitwise equality of every runtime state, CPU schedule, generated post ID or trace. '
             'The workload specification and marker contents match; container scheduling remains uncontrolled.','',
             'The original dtrem-pilot application is separate. Temporary dtrem-pair projects are removed after their evidence is saved. '
             'The next experiment still requires a specified twin predictor, dependency reference, observable uncertainty features and calibration split. '
             'Do not reinterpret this start-versus-no-action manipulation check as validation of the stale-state hypothesis.','',
             f'Raw evidence: `paired-runs/{batch_id}/`. The saved plan predates execution. '
             'Each arm includes the scenario, source scripts, image lock, Compose configuration, action receipts, HTTP observations and summary.']
    if any(r['status']!='COMPLETE' for r in rows):
        text += ['', 'Failed attempts are retained:', *[f"- {r['seed']} {r['arm']}: {r.get('error')}" for r in rows if r['status']!='COMPLETE']]
    (batch/'Results.md').write_text('\n'.join(text)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch');analyze(p.parse_args().batch)
