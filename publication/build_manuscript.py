"""Generate standalone LaTeX tables from audited development-stage analyses."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
STAGES={
    'direct':'direct-runs/3049d39ca8b942858f518d4b5b2317b1',
    'sequential':'sequential-runs/5f71ebb803bd4d939e978b6e80eeecf5',
    'temporal':'temporal-runs/294bab8ce4274cb7b50c52b48b59c78b',
    'race':'race-runs/9494250949eb49d5a9bb33a82bc00d5d',
    'event':'aligned-event-runs/fc54dc7bbf804c07b54d357033a60c70'}
data={};provenance={}
for key,relative in STAGES.items():
    path=ROOT/'pilot'/relative/'analysis.json'
    raw=path.read_bytes();data[key]=json.loads(raw)
    assert data[key]['integrity_verified']
    provenance[key]={'path':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(raw).hexdigest()}

def safe(value):return str(value).replace('_',' ')
def table(headers,rows,caption):
    align='l'+'r'*(len(headers)-1)
    lines=[r'\begin{table}[ht]',r'\centering\small',r'\begin{tabular}{'+align+'}',r'\toprule',
           ' & '.join(headers)+r' \\',r'\midrule']
    lines+=[' & '.join(safe(x) for x in row)+r' \\' for row in rows]
    return '\n'.join(lines+[r'\bottomrule',r'\end{tabular}',r'\caption{'+caption+'}',r'\end{table}'])

tokens={}
tokens['DIRECT_TABLE']=table(['Policy','Approvals','Incorrect'],
    [(m['policy'],m['eligible'],m['false_approvals']) for m in data['direct']['metrics']],
    'Direct-obligation comparison, 18 shared action outcomes.')
tokens['SEQUENTIAL_TABLE']=table(['Mode','Approvals','Incorrect','Calls','Median ms'],
    [(m['mode'],m['approvals'],m['false_approvals'],m['probe_calls'],f"{m['median_probe_wall_ms']:.1f}") for m in data['sequential']['modes']],
    'Separate fresh instances for full and early-stop modes, six opportunities each.')
tokens['TEMPORAL_TABLE']=table(['Evidence','Approvals','Incorrect'],
    [(m['policy'],m['approvals'],m['false_approvals']) for m in data['temporal']['metrics']],
    'Temporal-placement experiment, six shared action outcomes.')
tokens['RACE_TABLE']=table(['Placement','Trials','Approvals','Incorrect'],
    [(m['condition'],m['trials'],m['approvals'],m['incorrect_approvals']) for m in data['race']['metrics']],
    'Changes during or after final verification, six fresh action trials.')
tokens['EVENT_TABLE']=table(['Policy','Approvals','Incorrect','Rejected recovery'],
    [(m['policy'],m['approvals'],m['incorrect_approvals'],m['unnecessary_abstentions']) for m in data['event']['metrics']],
    'Actual lifecycle history with controlled delivery transformations, eight shared action outcomes; late functional rechecking follows the fault.')
e={m['policy']:m for m in data['event']['metrics']}
def count(name):
    m=e[name];return f"{m['incorrect_approvals']} incorrect approvals among {m['approvals']} approvals"
tokens['EVENT_ABSTRACT']=f"Available events gave {count('events_available')}, and post-fault functional rechecking gave {count('late_functional_recheck')}. Delayed or dropped events each gave {count('events_delayed')}."
assert e['events_delayed']['approvals']==e['events_silently_dropped']['approvals'] and e['events_delayed']['incorrect_approvals']==e['events_silently_dropped']['incorrect_approvals']
tokens['EVENT_RESULT']=(f"Final functional evidence alone gave {count('final_checks')}. Adding fresh Running flags gave {count('fresh_running_state')}. "
    f"The available-event guard gave {count('events_available')}, with {e['events_available']['unnecessary_abstentions']} rejected opportunities that would have recovered. "
    f"The ten-second withholding and silent-drop variants each gave {count('events_delayed')}. "
    f"Late functional rechecking gave {count('late_functional_recheck')}. Thus this cohort does not establish an event-guard advantage over that stronger baseline. "
    'Event-action names and the complete per-trial decisions are retained in the machine-readable supplement.')
text=(ROOT/'overleaf/manuscript.template.tex').read_text(encoding='utf-8')
for name,value in tokens.items():
    assert '@@'+name+'@@' in text
    text=text.replace('@@'+name+'@@',value)
assert '@@' not in text and '\u2014' not in text
(ROOT/'overleaf/main.tex').write_text(text,encoding='utf-8')
provenance['main_tex_sha256']=hashlib.sha256(text.encode()).hexdigest()
(ROOT/'publication/manuscript-provenance.json').write_text(json.dumps(provenance,indent=2))
print(json.dumps({'source':str(ROOT/'overleaf/main.tex'),'tables_generated':5,'unresolved_template_tokens':0}))
