"""Package and independently replay the temporal experiment analysis."""
import hashlib
import json
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
batch_id=sys.argv[1]
assert len(batch_id)==32 and all(c in '0123456789abcdef' for c in batch_id)
batch=HERE/'temporal-runs'/batch_id
assert (batch/'analysis.json').exists() and (batch/'cleanup-verification.json').exists()
files={p.relative_to(ROOT).as_posix():p.read_bytes() for p in batch.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name in ('temporal_pilot.py','temporal_policy.py','test_temporal.py','analyze_temporal.py','Temporal verification design.md','package_temporal.py','verify_temporal_cleanup.py'):
    files['pilot/'+name]=(HERE/name).read_bytes()
files['licenses/DeathStarBench-LICENSE']=(ROOT/'data/DeathStarBench-LICENSE').read_bytes()
files['README.txt']=(
    'Temporal verification development evidence. Six live trials, three shadow policies sharing each outcome.\n'
    f'Replay without Docker: python pilot/analyze_temporal.py pilot/temporal-runs/{batch_id}\n'
    'Python standard library only. Verify payload hashes against MANIFEST.json.\n'
    'Source and plan frozen before execution; analysis code written while batch was running.\n'
    'Not a confirmatory study, final paper, novel algorithm, security test or atomicity guarantee.\n'
    'No faults are injected after the last check. Delays are collection-end to last-check-start, not action ages.\n'
    'Live reproduction requires separately obtained pinned images/runtime assets and bind-path adaptation.\n'
    'Archive retains original local paths, synthetic records, raw command evidence and upstream license.\n'
).encode()
manifest={n:hashlib.sha256(v).hexdigest() for n,v in sorted(files.items())}
archive=ROOT/'Temporal-verification-evidence-v0.1.zip'
assert not archive.exists(),'Use a new version instead of overwriting an existing bundle'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in sorted(files.items()):z.writestr(name,raw)
    z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
dest=HERE/'archive-replay'/('temporal-'+uuid.uuid4().hex)
dest.mkdir(parents=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in manifest.items())
    assert all((dest/n).resolve().is_relative_to(dest.resolve()) for n in z.namelist())
    z.extractall(dest)
relative=f'pilot/temporal-runs/{batch_id}'
before={name:(dest/relative/name).read_bytes() for name in ('analysis.json','Results.md')}
proc=subprocess.run([sys.executable,'-X','utf8','pilot/analyze_temporal.py',relative],cwd=dest,capture_output=True,text=True,timeout=60)
assert proc.returncode==0,proc.stdout+proc.stderr
assert all((dest/relative/n).read_bytes()==raw for n,raw in before.items())
result={'archive':str(archive),'payload_files':len(files),'bytes':archive.stat().st_size,
    'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_verified':True,
    'isolated_replay_identical':True,'replay_directory':str(dest)}
(batch/'archive-replay-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
