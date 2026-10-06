"""Package the author-review source and replayable evidence; never submit."""
import hashlib
import json
import re
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HERE=ROOT/'publication'
STAGES=[('direct-runs','3049d39ca8b942858f518d4b5b2317b1'),
        ('sequential-runs','5f71ebb803bd4d939e978b6e80eeecf5'),
        ('temporal-runs','294bab8ce4274cb7b50c52b48b59c78b'),
        ('race-runs','9494250949eb49d5a9bb33a82bc00d5d'),
        ('aligned-event-runs','fc54dc7bbf804c07b54d357033a60c70')]
source=(ROOT/'overleaf/main.tex').read_text(encoding='utf-8')
assert '@@' not in source and '\u2014' not in source
keys=set(re.findall(r'\\bibitem\{([^}]+)\}',source))
cited={k for group in re.findall(r'\\cite\{([^}]+)\}',source) for k in group.split(',')}
assert cited<=keys
stack=[]
for action,name in re.findall(r'\\(begin|end)\{([^}]+)\}',source):
    if action=='begin':stack.append(name)
    else:assert stack.pop()==name
assert not stack
abstract=source.split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]
checks={'citation_keys_resolved':True,'environments_balanced':True,'total_tables':source.count(r'\begin{table}'),'generated_analysis_tables':5,
        'unresolved_generation_tokens':False,'abstract_words':len(abstract.split()),'no_em_dashes':True,
        'compiled_pdf_verified':False,'author_fields_pending':True}
assert 150<=checks['abstract_words']<=250
(HERE/'source-checks.json').write_text(json.dumps(checks,indent=2))

def make_zip(path,files):
    assert not path.exists(),'Use a new version instead of replacing a prior bundle'
    manifest={k:hashlib.sha256(v).hexdigest() for k,v in sorted(files.items())}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):z.writestr(name,raw)
        z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in manifest.items())
    return {'path':str(path),'files':len(files),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

overleaf={'main.tex':(ROOT/'overleaf/main.tex').read_bytes(),'README.txt':(HERE/'README.txt').read_bytes()}
for name in ('Publication decision.md','Cover letter draft.txt','manuscript-provenance.json','source-checks.json','latex-build-status.json'):
    overleaf[name]=(HERE/name).read_bytes()
for stage,batch in STAGES:
    overleaf['tables-source/'+stage+'-analysis.json']=(ROOT/'pilot'/stage/batch/'analysis.json').read_bytes()
overleaf_result=make_zip(ROOT/'Overleaf-case-study-v0.2.zip',overleaf)

files={}
dirs=[ROOT/'pilot'/stage/batch for stage,batch in STAGES]
dirs += [ROOT/'pilot/direct-runs/b7f6534f0418437094f9a0e4052935a6',
         ROOT/'pilot/event-runs/7825aa3b0a7f453cbbb20201a8e43532',
         ROOT/'pilot/event-runs/0561985519f64e5999746c0006960374']
for directory in dirs:
    for path in directory.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
for path in (ROOT/'pilot').glob('*.py'):
    files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
for path in HERE.iterdir():
    if path.is_file():files[path.relative_to(ROOT).as_posix()]=path.read_bytes()
for name in ('main.tex','manuscript.template.tex'):
    files['overleaf/'+name]=(ROOT/'overleaf'/name).read_bytes()
for name in ('Experiments index.md','Event invalidation design.md','Aligned event comparison design.md','historical-action-scope-audit.json'):
    files['pilot/'+name]=(ROOT/'pilot'/name).read_bytes()
files['licenses/DeathStarBench-LICENSE']=(ROOT/'data/DeathStarBench-LICENSE').read_bytes()
commands=[['pilot/analyze_direct.py',STAGES[0][1]],
          *[[f'pilot/analyze_{name}.py',f'pilot/{stage}/{batch}'] for name,(stage,batch) in zip(('sequential','temporal','race','aligned_event'),STAGES[1:])],
          ['publication/build_manuscript.py']]
files['REPLAY.txt']=('\n'.join(['Python standard library; these commands do not launch Docker.','Run from the extracted root:',
    *['python '+' '.join(c) for c in commands],
    'Author-review draft, not submitted. No verified PDF build.',
    'Excluded attempts are retained at their original paths; do not pool their results.',
    'Live reruns require separate pinned runtime assets/images and host-path adaptation.'])+'\n').encode()
evidence_result=make_zip(ROOT/'Research-evidence-v0.2.zip',files)
dest=ROOT/'pilot/archive-replay'/('article-'+uuid.uuid4().hex)
dest.mkdir(parents=True)
with zipfile.ZipFile(evidence_result['path']) as z:
    assert all((dest/n).resolve().is_relative_to(dest.resolve()) for n in z.namelist())
    z.extractall(dest)
outputs=[f'pilot/{stage}/{batch}/{name}' for stage,batch in STAGES for name in ('analysis.json','Results.md')]
outputs+=['overleaf/main.tex','publication/manuscript-provenance.json']
before={n:(dest/n).read_bytes() for n in outputs}
for args in commands:
    run=subprocess.run([sys.executable,'-X','utf8',*args],cwd=dest,capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stdout+run.stderr
assert all((dest/n).read_bytes()==raw for n,raw in before.items())
result={'overleaf':overleaf_result,'evidence':evidence_result,'all_five_analyses_replayed_identically':True,
        'manuscript_regenerated_identically':True,'compiled_pdf_verified':False,'replay_directory':str(dest)}
(HERE/'package-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
