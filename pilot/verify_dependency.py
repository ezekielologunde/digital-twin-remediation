"""Supplemental manipulation and source-order checks, without changing outcome labels."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
batch_id=sys.argv[1]
assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
batch=HERE/'dependency-runs'/batch_id
rows=json.loads((batch/'summary.json').read_text())
checks=[]
for r in rows:
    assert r['status']=='COMPLETE'
    out=batch/f"{r['seed']}-{r['backend_condition']}-{r['arm']}"
    pred=json.loads((out/'predictions-before-action.json').read_text())
    s=pred['revalidated']['states']
    op=pred['revalidated']['operational_states']
    condition=r['backend_condition']
    assert not s['user-timeline-service']
    assert s['post-storage-service']==(condition!='down')
    assert op['post-storage-service']==(condition not in ('down','paused'))
    assert s['media-service']==(condition!='unrelated_down')
    assert pred['old']['states']['post-storage-service']
    events=[json.loads(l) for l in (out/'ledger.jsonl').read_text().splitlines()]
    sealed=next(i for i,e in enumerate(events) if e['kind']=='predictions_sealed')
    action=next(i for i,e in enumerate(events) if e['kind']=='docker' and e['args'][-2:]==['start','user-timeline-service'])
    assert sealed<action
    assert events[action]['returncode']==0
    checks.append({'seed':r['seed'],'condition':condition,'manipulation_verified':True,'action_receipt_after_seal':True})
report={'checks':checks,'complete':len(checks)==12,
        'boundary':'Receipt records command completion; source snapshots establish that command submission follows sealing.'}
(batch/'manipulation-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
