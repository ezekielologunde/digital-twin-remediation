"""Audit deterministic during/after-verification counterexamples."""
import argparse
import hashlib
import json
from pathlib import Path

def analyze(batch):
    rows=json.loads((batch/'summary.json').read_text())
    plan=json.loads((batch/'plan.json').read_text())
    assert len(rows)==len(plan['arms'])==6
    assert [[r['seed'],r['backend_condition']] for r in rows]==plan['arms']
    volumes=set();details=[]
    for r in rows:
        folder=batch/f"{r['seed']}-{r['backend_condition']}"
        assert r==json.loads((folder/'summary.json').read_text())
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        assert r['fresh_volume_ids'] and r['empty_before_initialization'] and r['baseline_markers_verified']==3
        assert all(v['verified'] for v in r['direct_baseline'].values())
        for file,key in [('ledger.jsonl','ledger_sha256'),('scenario.json','scenario_sha256'),('compose.json','compose_sha256')]:
            assert hashlib.sha256((folder/file).read_bytes()).hexdigest()==r[key]
        for name in ('race_pilot.py','race_probes.py','dependency_twin.py','validity_twin.py'):
            assert (folder/name).read_bytes()==(batch/name).read_bytes()
        events=[json.loads(line) for line in (folder/'ledger.jsonl').read_text().splitlines()]
        sealed=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
        assert sealed<action and events[action]['returncode']==0
        assert sealed<next(i for i,e in enumerate(events) if e['kind']=='outcome')
        raw=(folder/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==events[sealed]['sha256']
        pred=json.loads(raw); ev=r['final_evidence'];t=r['timings']
        assert pred['evidence']==ev and pred['prediction']==r['prediction']
        assert pred['timings']=={k:v for k,v in t.items() if k!='action_decision'}
        approve=all(ev[k]['verified'] is True for k in ('timeline_redis','timeline_mongo','post_storage'))
        assert approve==(r['prediction']['decision']=='approve')
        boundaries=[(i,e) for i,e in enumerate(events) if e['kind']=='probe_boundary']
        assert [e['name'] for i,e in boundaries]==['timeline_redis','timeline_mongo','post_storage']
        for i,e in boundaries:
            assert e['result']==ev[e['name']] and i<sealed
            assert events[i-1]['kind']=='docker' and events[i-1]['args'][0]=='exec'
            assert events[i-1]['returncode']==e['result']['returncode']
        redis=ev['timeline_redis']; mongo=ev['timeline_mongo']; post=ev['post_storage']
        assert t['final_start']<=redis['started_monotonic']<=redis['completed_monotonic']<=mongo['started_monotonic']<=mongo['completed_monotonic']<=post['started_monotonic']<=post['completed_monotonic']<=t['final_end']<=t['action_decision']
        condition=r['backend_condition']
        faults=[i for i,e in enumerate(events) if e['kind']=='fault_boundary']
        if condition=='during_final':
            assert len(faults)==1 and boundaries[0][0]<faults[0]<boundaries[1][0]
            assert redis['completed_monotonic']<=t['fault_start']<t['fault_confirmed']<=mongo['started_monotonic']
        elif condition=='after_final':
            assert len(faults)==1 and boundaries[-1][0]<faults[0]<sealed
            assert t['final_end']<=t['fault_start']<t['fault_confirmed']<=t['action_decision']
        else:
            assert condition=='none' and not faults and 'fault_start' not in t
        obs=r['outcome_observations']
        contract=len(obs)>=2 and all(v['classification']=='verified_readback' and v['elapsed_s']<=8 for v in obs[-2:]) and not any(v['classification']=='creator_mismatch' for v in obs)
        assert contract==r['contract_met']
        assert r['post_action_states']['user-timeline-redis']==(condition=='none')
        assert r['post_action_states']['user-timeline-mongodb']
        assert not volumes.intersection(r['volume_names']);volumes.update(r['volume_names'])
        details.append({'seed':r['seed'],'condition':condition,'all_checks_passed':approve,
            'decision':r['prediction']['decision'],'contract_met':contract,
            'probe_age_at_action_s':{k:t['action_decision']-v['completed_monotonic'] for k,v in ev.items()},
            'collection_end_age_s':t['action_decision']-t['final_end']})
    metrics=[]
    for condition in ('none','during_final','after_final'):
        group=[r for r in details if r['condition']==condition]
        metrics.append({'condition':condition,'trials':len(group),'approvals':sum(r['all_checks_passed'] for r in group),
            'incorrect_approvals':sum(r['all_checks_passed'] and not r['contract_met'] for r in group),
            'recoveries':sum(r['contract_met'] for r in group)})
    result={'batch':batch.name,'integrity_verified':True,'distinct_volume_ids':len(volumes),'metrics':metrics,'details':details,
        'limitations':'Deterministic fault scheduling with a blocking hook, two synthetic account blocks, known Redis stop, fixed order. Not natural race incidence, a novel algorithm, a coherence proof, or a test of concurrency control.'}
    (batch/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Changes during and after final verification','','Development experiment, 5 October 2026. Six fresh instances across two account blocks. The verifier approves only when all three recorded final checks succeed. Fault placement is not a policy input.','',
        '| Placement of Redis stop | Trials | Approvals | Incorrect approvals | Recovery contracts met |','|---|---:|---:|---:|---:|']
    for m in metrics:
        lines.append(f"| {m['condition']} | {m['trials']} | {m['approvals']} | {m['incorrect_approvals']} | {m['recoveries']} |")
    lines+=['','| Block | Condition | All checks passed | Recovery contract | Redis check age at action (s) | Whole collection end age (s) |','|---|---|---|---|---:|---:|']
    for r in details:
        lines.append(f"| {r['seed']} | {r['condition']} | {r['all_checks_passed']} | {r['contract_met']} | {r['probe_age_at_action_s']['timeline_redis']:.3f} | {r['collection_end_age_s']:.3f} |")
    lines+=['','During-collection injection is a deliberately blocking hook: Redis is stopped after its successful check and before MongoDB is checked. After-collection injection occurs once all checks have completed. These are controlled counterexamples, not samples of natural concurrent failures.','',
        'A small age measured from completion of the whole collection can conceal an older individual Redis result. Individual probe completion ages are recorded in analysis.json. All dependencies were healthy initially; this study does not show they were never simultaneously healthy.','',
        'The recorded approval is sealed before target-only restart. The injector knows the fault; the verifier receives only check results. An observer using additional fresh container state might abstain, but that stronger policy is not evaluated here. Neither a locking/lease defense nor a deployed gate is implemented.','',
        'Integrity audit covers raw event order, per-probe timestamps, source/configuration/ledger hashes, sealed evidence, independently recomputed outcomes, action scope, independent volumes and cleanup return codes. Live resource absence is verified separately.','',result['limitations']]
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',type=Path)
    print(json.dumps(analyze(p.parse_args().batch),indent=2))
