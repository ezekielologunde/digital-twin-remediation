"""Integrity audit and descriptive analysis of timed evidence invalidation."""
import argparse
import hashlib
import json
from pathlib import Path
from temporal_policy import decisions

def analyze(batch):
    rows=json.loads((batch/'summary.json').read_text())
    plan=json.loads((batch/'plan.json').read_text())
    assert len(rows)==len(plan['arms'])==6
    assert [[r['seed'],r['backend_condition'],r['delay_s']] for r in rows]==plan['arms']
    volumes=set();details=[]
    for r in rows:
        folder=batch/f"{r['seed']}-{r['backend_condition']}-{r['delay_s']}"
        assert r==json.loads((folder/'summary.json').read_text())
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        assert r['fresh_volume_ids'] and r['empty_before_initialization'] and r['baseline_markers_verified']==3
        for file,key in [('ledger.jsonl','ledger_sha256'),('scenario.json','scenario_sha256'),('compose.json','compose_sha256')]:
            assert hashlib.sha256((folder/file).read_bytes()).hexdigest()==r[key]
        for name in ('temporal_pilot.py','temporal_policy.py','sequential_probes.py','dependency_twin.py','validity_twin.py'):
            assert (folder/name).read_bytes()==(batch/name).read_bytes()
        events=[json.loads(x) for x in (folder/'ledger.jsonl').read_text().splitlines()]
        sealed=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
        action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
        assert sealed<action and events[action]['returncode']==0
        assert sealed<next(i for i,e in enumerate(events) if e['kind']=='outcome')
        raw=(folder/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==events[sealed]['sha256']
        pred=json.loads(raw); ev=r['temporal_evidence'];t=r['timings']
        assert pred['evidence']==ev and pred['predictions']==r['predictions']==decisions(ev['cached'],ev['refresh'],ev['last'])
        assert pred['timings']=={k:v for k,v in t.items() if k!='action_decision'}
        assert all(v['verified'] for v in ev['cached'].values())
        assert t['cached_end']<=t['refresh_start']<t['refresh_end']<=t['last_check_start']<t['last_check_end']<=t['action_decision']
        hold=t['last_check_start']-t['refresh_end']
        assert r['delay_s']-0.01<=hold<=r['delay_s']+0.5
        condition=r['backend_condition']
        if condition=='before_refresh':
            assert t['cached_end']<=t['fault_command_start']<t['fault_verified_stopped']<=t['refresh_start']
        elif condition=='after_refresh':
            assert t['refresh_end']<=t['fault_command_start']<t['fault_verified_stopped']<=t['last_check_start']
        else:
            assert condition=='none' and 'fault_command_start' not in t
        # Cross-check actual middle and final command blocks against evidence.
        middle=next(i for i,e in enumerate(events) if e['kind']=='temporal_refresh')
        assert events[middle]['results']==ev['refresh']
        before=[e for e in events[:middle] if e['kind']=='docker' and e['args'][0]=='exec'][-3:]
        after=[e for e in events[middle+1:sealed] if e['kind']=='docker' and e['args'][0]=='exec']
        assert len(before)==len(after)==3
        for group,values in ((before,ev['refresh']),(after,ev['last'])):
            for e,k in zip(group,('timeline_redis','timeline_mongo','post_storage')):
                assert e['returncode']==values[k]['returncode']
        obs=r['outcome_observations']
        contract=len(obs)>=2 and all(v['classification']=='verified_readback' and v['elapsed_s']<=8 for v in obs[-2:]) and not any(v['classification']=='creator_mismatch' for v in obs)
        assert contract==r['contract_met']
        assert r['post_action_states']['user-timeline-redis']==(condition=='none')
        assert r['post_action_states']['user-timeline-mongodb']
        assert not volumes.intersection(r['volume_names']);volumes.update(r['volume_names'])
        details.append({'condition':condition,'assigned_wait_s':r['delay_s'],'actual_wait_s':hold,
            'cached_group_age_at_action_s':t['action_decision']-t['cached_end'],
            'middle_group_age_at_action_s':t['action_decision']-t['refresh_end'],
            'last_group_age_at_action_s':t['action_decision']-t['last_check_end'],
            'decisions':r['predictions'],'contract_met':contract})
    metrics=[]
    for policy in plan['policies']:
        approved=[r for r in rows if r['predictions'][policy]['decision']=='approve']
        errors=sum(not r['contract_met'] for r in approved)
        metrics.append({'policy':policy,'approvals':len(approved),'false_approvals':errors,
            'true_approvals':len(approved)-errors,'expected_false_at_two_approvals':2*errors/len(approved) if len(approved)>=2 else None})
    result={'batch':batch.name,'live_trials':6,'independent_policy_trials':False,'integrity_verified':True,
        'distinct_volume_ids':len(volumes),'metrics':metrics,'details':details,
        'limits':'One trial per delay/placement cell. Shared probes and outcomes. Collection-end ages underestimate the age of earlier individual probes. No fault occurs after final verification; no atomicity or general reliability claim.'}
    (batch/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Temporal evidence invalidation results','','Development manipulation study, 4 October 2026. Six fresh instances, three placements of a Redis stop and two waiting periods. Each trial supplies one action outcome shared by three shadow evidence policies.','',
        '| Evidence policy | Approvals | Incorrect approvals | Correct approvals | Expected incorrect at two approvals |',
        '|---|---:|---:|---:|---:|']
    for m in metrics:
        lines.append(f"| {m['policy']} | {m['approvals']} | {m['false_approvals']} | {m['true_approvals']} | {m['expected_false_at_two_approvals']:.2f} |")
    lines+=['','The last column is a secondary exploratory comparison: the exact expectation under uniform thinning to two approvals, conditional on these outcomes. It is not a new experiment, confidence interval, or risk guarantee.','',
        '| Fault placement | Assigned wait (s) | Actual wait (s) | Cached decision | Middle refresh | Final refresh | Recovery contract |',
        '|---|---:|---:|---|---|---|---|']
    for r in details:
        d=r['decisions']
        lines.append(f"| {r['condition']} | {r['assigned_wait_s']} | {r['actual_wait_s']:.3f} | {d['cached']['decision']} | {d['refresh_before_wait']['decision']} | {d['last_moment_refresh']['decision']} | {r['contract_met']} |")
    lines+=['','The assigned wait is measured from middle-collection completion to final-collection start, not to the action. Actual collection-end-to-action ages are in analysis.json. Earlier probes within each sequential collection are older than that group age.','',
        'Integrity checks cover source/configuration hashes, recorded arm order, command receipts, sealed predictions, fault/probe ordering, timing tolerance, independent outcome recomputation, target-only dependency state, fresh volume identities and cleanup return codes. Live absence is verified separately.','',
        result['limits'],'',
        'Interpretation: a controlled state change can invalidate previously successful verification. Detecting changes before the final recheck does not demonstrate protection against a later change. These known-fault examples do not estimate a time-to-expiry threshold or establish research novelty.']
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',type=Path)
    print(json.dumps(analyze(p.parse_args().batch),indent=2))
