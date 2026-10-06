"""Package local evidence and replayable analysis, without claiming portable deployment."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
batch_id=sys.argv[1]
assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
batch=HERE/'challenge-runs'/batch_id
assert (batch/'analysis.json').is_file() and (batch/'cleanup-verification.json').is_file()
files={str(p.relative_to(ROOT)).replace('\\','/'):p.read_bytes()
       for p in batch.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name in ('analyze_challenge.py','analyze_dependency.py','challenge_twin.py','dependency_twin.py','validity_twin.py','test_challenge.py','Functional challenge design.md'):
    p=HERE/name
    files['pilot/'+name]=p.read_bytes()
files['licenses/DeathStarBench-LICENSE']=(ROOT/'data'/'DeathStarBench-LICENSE').read_bytes()
for name in ('Novelty checkpoint.md','manifest.json'):
    p=ROOT/'literature'/'challenge-monitoring'/name
    files['literature/challenge-monitoring/'+name]=p.read_bytes()
files['README.txt']=(
    'Development evidence bundle, not a final journal manuscript or portable deployment.\n'
    f'Batch: {batch_id}\n'
    f'Replay descriptive analysis from the extracted root: python pilot/analyze_challenge.py {batch_id}\n'
    'Python standard library only. Analysis asserts integrity and does not launch Docker.\n'
    'To verify content, compare SHA256 of each payload file against MANIFEST.json.\n'
    'Raw Docker and HTTP ledgers contain synthetic benchmark data and original local paths.\n'
    'Archived Compose bind mounts refer to the original host. Live reproduction requires the\n'
    'pinned benchmark runtime files, Docker images, path adaptation and isolated project setup.\n'
    'No Docker images or persistent database volumes are included. The source excerpt retains\n'
    'its upstream Apache 2.0 license; its provenance is in dependency-audit/witness.json.\n'
    'Twelve shared action outcomes are not thirty-six independent policy trials.\n'
).encode()
manifest={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())}
archive=ROOT/'Functional-challenge-evidence-v0.1.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in sorted(files.items()):z.writestr(name,raw)
    z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(name)).hexdigest()==sha for name,sha in manifest.items())
print(json.dumps({'archive':str(archive),'payload_files':len(files),'bytes':archive.stat().st_size,
                  'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
