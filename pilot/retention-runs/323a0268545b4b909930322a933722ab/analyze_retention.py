"""Audit event-retention experiments from immutable receipts."""
import argparse,hashlib,json
from pathlib import Path
from aligned_event_policy import decide
from probe import classify_read
POLICIES=('final_checks','fresh_running_state','events_available','late_functional_recheck')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def analyze(batch):
 plan=json.loads((batch/'plan.json').read_text());rows=json.loads((batch/'summary.json').read_text())
 assert len(rows)==len(plan['arms'])
 assert [[r['seed'],r['backend_condition']] for r in rows]==plan['arms']
 volumes=set();details=[]
 for r in rows:
  d=batch/f"{r['seed']}-{r['backend_condition']}"
  assert r==json.loads((d/'summary.json').read_text())
  assert r['status']=='COMPLETE' and r['cleanup_returncode']==0
  assert r['empty_before_initialization'] and r['baseline_markers_verified']==3
  assert r['fresh_volume_ids'] and not volumes.intersection(r['volume_names']);volumes.update(r['volume_names'])
  for name,key in [('ledger.jsonl','ledger_sha256'),('scenario.json','scenario_sha256'),('compose.json','compose_sha256'),('witness.jsonl','witness_sha256')]:assert sha(d/name)==r[key]
  ev=[json.loads(l) for l in (d/'ledger.jsonl').read_text().splitlines()]
  seal=next(i for i,e in enumerate(ev) if e['kind']=='predictions_sealed')
  act=next(i for i,e in enumerate(ev) if e['kind']=='docker' and e['args']==['start',r['target_container_id']])
  assert seal<act and ev[act]['returncode']==0
  assert sha(d/'predictions-before-action.json')==ev[seal]['sha256']
  pred=json.loads((d/'predictions-before-action.json').read_text());x=r['event_inputs']
  assert pred['event_inputs']==x and pred['predictions']==r['predictions'] and pred['evidence']==r['final_evidence']
  assert all(v['verified'] for v in r['final_evidence'].values())
  q=[e for e in ev[:seal] if e['kind']=='docker' and e['args'][0]=='events'];assert len(q)==2
  actual=[json.loads(l) for l in q[-1]['stdout'].splitlines() if l.strip()];assert actual==x['events']
  computed,changes=decide(r['final_evidence'],actual,set(x['dependency_ids']),x['cursor'],x['running'],x['delayed_available_at'],x['decision_time'],x['late_evidence'])
  assert {k:computed[k] for k in POLICIES}==r['predictions']
  witness=[json.loads(l) for l in (d/'witness.jsonl').read_text().splitlines()]
  ret=r['retention'];stop=ret['stop_witness']
  if ret['faulted']:
   assert stop in witness and stop['Action']=='stop' and stop['Actor']['ID'] in x['dependency_ids'] and int(stop['timeNano'])>x['cursor']
   assert ret['stop_retained']==(stop in actual)
  else:assert stop is None and not ret['stop_retained']
  assert ret['eviction_verified']==(bool(stop) and stop not in actual)
  assert sum(e['kind']=='docker' and len(e['args'])==3 and e['args'][0]=='exec' and e['args'][2]=='true' for e in ev)==ret['churn_exec_calls']
  t=r['timings'];assert t['intervention_end']<=min(t['late_start'],t['query_start'])
  if ret['order']=='events_first':assert t['query_end']<=t['late_start']
  else:assert t['late_end']<=t['query_start']
  obs=r['outcome_observations'];raw=[e for e in ev if e['kind']=='http' and e['phase']=='outcome_read'];recorded=[e for e in ev if e['kind']=='outcome']
  scenario=json.loads((d/'scenario.json').read_text());assert len(obs)==len(raw)==len(recorded)
  for o,a,b in zip(obs,raw,recorded):
   assert o['classification']==classify_read(a['status'],a['body'],scenario['markers'][-1],scenario['user_id'])
   assert all(o[k]==b[k] for k in ('elapsed_s','classification'))
  label=len(obs)>=2 and all(o['classification']=='verified_readback' and o['elapsed_s']<=8 for o in obs[-2:]) and not any(o['classification']=='creator_mismatch' for o in obs)
  assert label==r['contract_met']
  details.append({'seed':r['seed'],'condition':r['backend_condition'],'order':ret['order'],'recovered':label,'eviction_verified':ret['eviction_verified'],'stop_retained':ret['stop_retained'],'decisions':r['predictions'],'query_records':ret['query_records']})
 metrics=[]
 for condition in sorted(set(r['backend_condition'] for r in rows)):
  group=[r for r in rows if r['backend_condition']==condition]
  for policy in POLICIES:
   approved=[r for r in group if r['predictions'][policy]['decision']=='approve']
   metrics.append({'condition':condition,'policy':policy,'trials':len(group),'approvals':len(approved),'incorrect_approvals':sum(not r['contract_met'] for r in approved),'rejected_recovery':sum(r['contract_met'] and r['predictions'][policy]['decision']=='abstain' for r in group)})
 result={'integrity_verified':True,'trials':len(rows),'independent_volumes':len(volumes),'metrics':metrics,'details':details,'limits':'Known fault boundary, shadow decisions, fixed action, single host; no deployed-gate or generalization claim.'}
 (batch/'analysis.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('batch',type=Path);analyze(p.parse_args().batch)
