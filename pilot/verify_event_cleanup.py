"""Read-only verification of resource absence for the completed batch."""
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

batch=Path(sys.argv[1]).resolve()
rows=json.loads((batch/'summary.json').read_text())
assert len(rows)==8 and all(r['status']=='COMPLETE' and r['cleanup_returncode']==0 for r in rows)
def docker(*args):
    p=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=60,check=True)
    return p.stdout.splitlines()
volumes=set(docker('volume','ls','-q'))
checks=[]
for r in rows:
    project=r['project']
    assert project.startswith('dtrem-event-'+batch.name[:8]+'-')
    containers=docker('ps','-aq','--filter','label=com.docker.compose.project='+project)
    networks=docker('network','ls','-q','--filter','label=com.docker.compose.project='+project)
    remaining=sorted(volumes.intersection(r['volume_names']))
    checks.append({'project':project,'remaining_containers':containers,'remaining_networks':networks,'remaining_volumes':remaining})
    assert not containers and not networks and not remaining
original=docker('ps','-q','--filter','label=com.docker.compose.project=dtrem-pilot')
prior=batch.parents[1]/'direct-runs'/'3049d39ca8b942858f518d4b5b2317b1'/'summary.json'
prior_volumes={v for r in json.loads(prior.read_text()) for v in r['volume_names']}
prior2=batch.parents[1]/'sequential-runs'/'5f71ebb803bd4d939e978b6e80eeecf5'/'summary.json'
prior_volumes.update(v for r in json.loads(prior2.read_text()) for v in r['volume_names'])
prior3=batch.parents[1]/'temporal-runs'/'294bab8ce4274cb7b50c52b48b59c78b'/'summary.json'
prior_volumes.update(v for r in json.loads(prior3.read_text()) for v in r['volume_names'])
prior4=batch.parents[1]/'race-runs'/'9494250949eb49d5a9bb33a82bc00d5d'/'summary.json'
prior_volumes.update(v for r in json.loads(prior4.read_text()) for v in r['volume_names'])
excluded=batch.parents[1]/'event-runs'/'7825aa3b0a7f453cbbb20201a8e43532'/'summary.json'
prior_volumes.update(v for r in json.loads(excluded.read_text()) for v in r['volume_names'])
current_volumes={v for r in rows for v in r['volume_names']}
assert not prior_volumes.intersection(current_volumes)
result={'checked_utc':datetime.now(timezone.utc).isoformat(),'projects':checks,
    'original_pilot_running_containers':len(original),'distinct_new_volumes':len(current_volumes),
    'disjoint_from_prior_corrected_batches_and_excluded_attempt':True}
(batch/'cleanup-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'temporary_resources_remaining':0,'original_pilot_running_containers':len(original),'distinct_new_volumes':len(current_volumes)}))
