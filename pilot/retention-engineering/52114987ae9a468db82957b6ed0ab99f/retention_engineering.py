"""Engineering pilot only; no application recovery result is inferred."""
from pathlib import Path
import json,subprocess,time,uuid,hashlib,shutil
from retention_witness import Witness
HERE=Path(__file__).resolve().parent
out=HERE/'retention-engineering'/uuid.uuid4().hex;out.mkdir(parents=True)
project='dtrem-retention-pilot-'+out.name[:12]
ids=[];w=None;result={'project':project,'status':'FAILED','research_trials':0}
def docker(args):
    r=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=30)
    with (out/'commands.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'args':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})+'\n')
    r.check_returncode();return r.stdout.strip()
def history():
    now=time.time_ns();end=f'{now//10**9}.{now%10**9:09d}'
    return [json.loads(x) for x in docker(['events','--since',str(start),'--until',end,'--filter','label=com.docker.compose.project='+project,'--format','{{json .}}']).splitlines()]
try:
    image=docker(['image','inspect','redis:latest','--format','{{.Id}}'])
    result['image_id']=image;result['docker_version']=docker(['version','--format','{{.Server.Version}}'])
    start=int(time.time())-1
    for role in ('dependency','noise'):
        ids.append(docker(['run','-d','--network','none','--memory','64m','--cpus','0.25','--label','com.docker.compose.project='+project,'--name',project+'-'+role,image,'sleep','600']))
    w=Witness(project,out/'witness.jsonl')
    # Handshake is a observed lifecycle event, not an assumed subscription delay.
    time.sleep(.5)
    docker(['rename',ids[1],project+'-ready']);w.wait(ids[1],'rename')
    docker(['stop','--time','1',ids[0]]);stop=w.wait(ids[0],'stop')
    before=history();assert any(e.get('Action')=='stop' and e.get('Actor',{}).get('ID')==ids[0] for e in before)
    for _ in range(100):docker(['exec',ids[1],'true'])
    docker(['rename',ids[1],project+'-finished']);w.wait(ids[1],'rename')
    after=history()
    absent=not any(e.get('Action')=='stop' and e.get('Actor',{}).get('ID')==ids[0] for e in after)
    result.update(status='COMPLETE',churn_exec_calls=100,stop_witnessed=True,stop_present_before=True,stop_absent_after=absent,bounded_records=len(after),witness_records=len(w.rows))
    (out/'history-before.json').write_text(json.dumps(before,indent=2))
    (out/'history-after.json').write_text(json.dumps(after,indent=2))
finally:
    if w:w.close()
    for cid in ids:
        assert docker(['inspect',cid,'--format','{{index .Config.Labels "com.docker.compose.project"}}'])==project
        docker(['rm','-f','-v',cid])
    result['cleanup_verified']=not docker(['ps','-aq','--filter','label=com.docker.compose.project='+project])
    for name in ('retention_engineering.py','retention_witness.py'):shutil.copy2(HERE/name,out/name)
    result['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'path':str(out),**result},indent=2))
