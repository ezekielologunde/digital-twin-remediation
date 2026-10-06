"""Audit and summarize separate-instance full versus early-stop development trials."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path


def analyze(batch):
    rows=json.loads((batch/'summary.json').read_text())
    plan=json.loads((batch/'plan.json').read_text())
    assert len(rows)==len(plan['arms'])==12, 'Incomplete batch must not be scored as complete'
    assert [[r['seed'],r['backend_condition'],r['mode']] for r in rows]==plan['arms']
    volumes=set()
    for r in rows:
        folder=batch/f"{r['seed']}-{r['backend_condition']}-{r['mode']}"
        assert r==json.loads((folder/'summary.json').read_text())
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        assert r['fresh_volume_ids'] and r['empty_before_initialization'] and r['baseline_markers_verified']==3
        assert r['functional_baseline_verified'] and all(v['verified'] for v in r['direct_baseline'].values())
        for name,key in [('scenario.json','scenario_sha256'),('compose.json','compose_sha256'),('ledger.jsonl','ledger_sha256')]:
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==r[key]
        for name in ('sequential_pilot.py','sequential_probes.py','dependency_twin.py','validity_twin.py'):
            assert (folder/name).read_bytes()==(batch/name).read_bytes()
        events=[json.loads(x) for x in (folder/'ledger.jsonl').read_text().splitlines()]
        seal=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
        assert seal<action and events[action]['returncode']==0
        assert seal<next(i for i,e in enumerate(events) if e['kind']=='outcome')
        raw=(folder/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==events[seal]['sha256']
        pred=json.loads(raw)
        assert pred['direct_probes']==r['direct_probes'] and pred['predictions']==r['predictions']
        keys=('timeline_redis','timeline_mongo','post_storage')
        probes=r['direct_probes']; seen_failure=False; executed=0
        for k in keys:
            v=probes[k]
            if r['mode']=='early_stop' and seen_failure:
                assert not v['executed'] and v['verified'] is None
            else:
                assert v['executed'] and isinstance(v['verified'],bool)
                executed+=1; seen_failure=seen_failure or not v['verified']
        lower=next(i for i,e in enumerate(events) if e.get('phase')=='functional_probe_before_action')
        upper=next(i for i,e in enumerate(events) if e['kind']=='direct_probes_before_action')
        calls=[e for e in events[lower+1:upper] if e['kind']=='docker']
        assert len(calls)==executed and all(e['args'][0]=='exec' for e in calls)
        approve=all(probes[k]['verified'] is True for k in keys)
        assert approve==(r['predictions']['direct_dependencies']['decision']=='approve')
        obs=r['outcome_observations']
        contract=len(obs)>=2 and all(v['classification']=='verified_readback' and v['elapsed_s']<=8 for v in obs[-2:]) and not any(v['classification']=='creator_mismatch' for v in obs)
        assert contract==r['contract_met']
        condition=r['backend_condition']
        for service,expected in [('user-timeline-mongodb',condition not in ('timeline_mongo_down','mongo_down_short')),('user-timeline-redis',condition!='timeline_redis_down')]:
            assert pred['revalidated']['states'][service]==expected==r['post_action_states'][service]
        assert not volumes.intersection(r['volume_names']);volumes.update(r['volume_names'])
    modes=[]
    for mode in ('full','early_stop'):
        group=[r for r in rows if r['mode']==mode]
        approved=[r for r in group if r['predictions']['direct_dependencies']['decision']=='approve']
        modes.append({'mode':mode,'trials':len(group),'approvals':len(approved),
            'false_approvals':sum(not r['contract_met'] for r in approved),
            'contract_met':sum(r['contract_met'] for r in group),
            'probe_calls':sum(v['executed'] for r in group for v in r['direct_probes'].values()),
            'median_probe_wall_ms':statistics.median(r['direct_probe_wall_ms'] for r in group),
            'sum_probe_wall_ms':sum(r['direct_probe_wall_ms'] for r in group)})
    pairs=[]
    for condition in sorted({r['backend_condition'] for r in rows}):
        f=next(r for r in rows if r['backend_condition']==condition and r['mode']=='full')
        s=next(r for r in rows if r['backend_condition']==condition and r['mode']=='early_stop')
        pairs.append({'condition':condition,'full_ms':f['direct_probe_wall_ms'],'early_stop_ms':s['direct_probe_wall_ms'],
            'difference_ms':f['direct_probe_wall_ms']-s['direct_probe_wall_ms'],
            'same_decision':f['predictions']['direct_dependencies']==s['predictions']['direct_dependencies'],
            'same_contract_outcome':f['contract_met']==s['contract_met']})
    result={'batch':batch.name,'integrity_verified':True,'distinct_volume_ids':len(volumes),'modes':modes,'conditions':pairs,
        'boundary':'One separately reset instance per mode and condition, descriptive timing only; known faults and fixed order. Not an adaptive method or causal population speedup estimate.'}
    (batch/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Sequential verification results','','Development study, 4 October 2026. Twelve fresh instances, six conditions and two modes. Approval requires all three checks; early stopping abstains at the first failed check. Unexecuted checks remain unknown.','',
        '| Mode | Trials | Approvals | False approvals | Executed checks | Median direct-check block (ms) |',
        '|---|---:|---:|---:|---:|---:|']
    for m in modes:
        lines.append(f"| {m['mode']} | {m['trials']} | {m['approvals']} | {m['false_approvals']} | {m['probe_calls']} | {m['median_probe_wall_ms']:.1f} |")
    lines+=['','| Condition | Full (ms) | Early stop (ms) | Full minus early stop (ms) | Same decision and outcome |','|---|---:|---:|---:|---|']
    for p in pairs:
        lines.append(f"| {p['condition']} | {p['full_ms']:.1f} | {p['early_stop_ms']:.1f} | {p['difference_ms']:.1f} | {p['same_decision'] and p['same_contract_outcome']} |")
    lines+=['','These are actual elapsed direct-collector durations including command logging. Both modes have common initialization and functional probing outside this interval. Durations exclude baseline acquisition, fault setup, subsequent snapshots and recovery. Each condition has only one trial per mode; account identity is held fixed and data volumes are independent. Timing differences can reflect machine load, Docker client overhead and other environmental variation. No significance, general speedup, production risk bound or security claim is made.','',
        'Actions executed even when the verifier abstained. Outcomes assess whether approval would have been correct, not the effectiveness of a deployed gate. The eight-second recovery contract is availability and content verification, not attack containment.','',
        'Integrity checks cover recorded plan order, source/configuration hashes, complete baseline checks, sealed predictions before action, actual calls and skipped checks, independently recomputed outcome labels, target-only state checks, unique volumes and cleanup return codes. Live resource absence is recorded separately.','',result['boundary']]
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('batch',type=Path)
    print(json.dumps(analyze(parser.parse_args().batch),indent=2))
