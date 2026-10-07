"""Additional release audit: frozen code, cleanup receipts, and endpoint prefixes."""
from pathlib import Path
import argparse,collections,hashlib,json,subprocess
from analyze_sensitivity import endpoint

def verify(batch,live=False):
 plan=json.loads((batch/'plan.json').read_text());rows=json.loads((batch/'summary.json').read_text())
 assert len(rows)==24
 for name,h in plan['source_sha256'].items():assert hashlib.sha256((batch/name).read_bytes()).hexdigest()==h
 for name,h in plan['dependency_audit_sha256'].items():assert hashlib.sha256((batch/'dependency-audit'/name).read_bytes()).hexdigest()==h
 orders=collections.Counter((r['backend_condition'],r['retention']['order']) for r in rows)
 assert len(orders)==8 and set(orders.values())=={3}
 allvol=[];checks=[]
 for r in rows:
  folder=batch/f"{r['seed']}-{r['backend_condition']}"
  for name,h in plan['source_sha256'].items():
   if (folder/name).exists():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==h
  allvol+=r['volume_names']
  if live:
   for kind,filter_value in [('ps','label=com.docker.compose.project='+r['project']),('network','label=com.docker.compose.project='+r['project'])]:
    args=['docker','ps','-aq','--filter',filter_value] if kind=='ps' else ['docker','network','ls','-q','--filter',filter_value]
    x=subprocess.run(args,capture_output=True,text=True,check=True,timeout=15);assert not x.stdout.strip()
  for h in (4,6,8):
   for k in (1,2,3):checks.append({'seed':r['seed'],'condition':r['backend_condition'],'horizon':h,'reads':k,'label':endpoint(r['outcome_observations'],h,k),'original':r['contract_met']})
 assert len(allvol)==len(set(allvol))==312
 if live:
  current=set(subprocess.check_output(['docker','volume','ls','-q'],text=True).splitlines());assert not current.intersection(allvol)
 result={'frozen_sources_verified':True,'balanced_orders':True,'distinct_volume_ids':len(allvol),'live_cleanup_verified':live,'sensitivity_cells':len(checks),'sensitivity_unchanged':all(x['label']==x['original'] for x in checks),'sensitivity_details':checks}

 if live:(batch/'release-audit.json').write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='sensitivity_details'}));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('batch',type=Path);p.add_argument('--live-cleanup',action='store_true');a=p.parse_args();verify(a.batch,a.live_cleanup)
