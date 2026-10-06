"""Descriptive shadow-policy analysis; controls are not start-action labels."""
import hashlib
import json
import sys
from pathlib import Path

def analyze(batch_id):
    assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
    batch=Path(__file__).resolve().parent/'validity-runs'/batch_id
    rows=json.loads((batch/'summary.json').read_text())
    plan=json.loads((batch/'plan.json').read_text())
    assert len(rows)==len(plan['arms'])==8
    volumes=set()
    for r in rows:
        assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
        out=batch/f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
        raw=(out/'ledger.jsonl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['ledger_sha256']
        records=[json.loads(line) for line in raw.decode().splitlines()]
        seal=next(i for i,e in enumerate(records) if e['kind']=='predictions_sealed')
        assert seal<next(i for i,e in enumerate(records) if e['kind']=='outcome')
        pred_raw=(out/'predictions-before-action.json').read_bytes()
        assert hashlib.sha256(pred_raw).hexdigest()==records[seal]['sha256']
        assert json.loads(pred_raw)['predictions']==r['predictions']
        current=set(r['volume_names'])
        assert current and not current & volumes
        volumes.update(current)
        assert r['fresh_volume_ids'] and r['empty_before_initialization']
    for seed in (201,202):
        for condition in ('up','down'):
            pair=[r for r in rows if r['seed']==seed and r['backend_condition']==condition]
            assert len(pair)==2 and len({r['scenario_sha256'] for r in pair})==1
    counts={}
    for r in rows:
        if r['arm']!='start': continue
        for view in r['predictions']:
            for policy in ('baseline','age_gate','revalidation'):
                cell=counts.setdefault((view['view'],policy),dict(n=0,approve=0,reject=0,abstain=0,false_approvals=0,valid_rejected=0))
                cell['n']+=1
                decision=view[policy]['decision']
                cell[decision]+=1
                cell['false_approvals']+=int(decision=='approve' and not r['contract_met'])
                cell['valid_rejected']+=int(decision=='reject' and r['contract_met'])
    table=[dict(view=v,policy=p,**c) for (v,p),c in counts.items()]
    report=dict(batch=batch_id,integrity_verified=True,distinct_volume_ids=len(volumes),arms=len(rows),start_opportunities=4,shadow_results=table)
    (batch/'analysis.json').write_text(json.dumps(report,indent=2))
    lines=['# Recovery-validity diagnostic','',
      '4 October 2026. Eight live arms, including four start interventions and four matched no-action controls. Each arm used fresh storage. Predictions were sealed before outcome observations. All ledgers and prediction seals matched their hashes; scenario hashes matched within pairs; storage identifiers were disjoint.','',
      'The contract requires the last two scheduled readbacks to verify the expected content and creator within eight seconds, with no observed creator mismatch. This measures recovery validity, not collateral damage or security-policy safety.','',
      '| Seed | Storage service | Action | Contract met | First verified read |',
      '|---|---|---|---|---|']
    for r in rows:
        t=r['first_verified_read_from_decision_s']
        lines.append(f"| {r['seed']} | {r['backend_condition']} | {r['arm']} | {r['contract_met']} | {str(round(t,3))+' s' if t is not None else 'Not observed'} |")
    lines+=['','Only start interventions label the candidate start action. Controls are not included in approval scores. Four evidence views reuse each outcome; they are not independent replications.','',
      '| Evidence view | Policy | Approved / opportunities | False recovery approvals / approved | Rejected | Abstained |',
      '|---|---|---|---|---|---|']
    for c in table:
        risk=f"{c['false_approvals']} / {c['approve']}" if c['approve'] else 'Undefined (no approvals)'
        lines.append(f"| {c['view']} | {c['policy']} | {c['approve']} / {c['n']} | {risk} | {c['reject']} | {c['abstain']} |")
    lines+=['',
      'These are shadow decisions: every planned intervention was executed regardless of its prediction. Counts do not demonstrate the benefit of a deployed policy. Revalidation rereads container running states using the same graph. The age gate abstains above one second; stale snapshots were retained for at least two seconds. Neither threshold is calibrated.','',
      'The reference graph is partial observed instrumentation, not complete ground truth. Masking deliberately deletes the timeline-to-storage edge. It is not random missingness. The baseline treats absent edges as absent dependencies and running containers as available services. These are strong assumptions.','',
      'A failure caused by this selected omission is an expected weakness of the baseline, not evidence of a novel algorithm or confirmation of the proposed interaction hypothesis. Two seeds and one dependency cannot support general effectiveness or statistical claims. Approval coverage differs across policies, so risk comparisons are not matched-coverage comparisons.','',
      'Next: use an independent graph-discovery or dependency challenge mechanism; compare at matched approval coverage; expand fault types, workloads, delay levels and randomly selected edge omissions under a frozen protocol. Add collateral-effect measurements before making safety claims. Public datasets still provide contextual validation, not the live remediation outcome labels in this diagnostic.']
    (batch/'Results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': analyze(sys.argv[1])
