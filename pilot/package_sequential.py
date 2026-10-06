"""Freeze raw evidence and verify both analyses from an isolated extraction."""
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
batch=HERE/'sequential-runs'/batch_id
assert (batch/'analysis.json').exists() and (batch/'cleanup-verification.json').exists()
files={}
for directory in (batch,HERE/'refresh-replay',HERE/'direct-runs'/'3049d39ca8b942858f518d4b5b2317b1'):
    for p in directory.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
for name in ('replay_refresh.py','test_refresh.py','analyze_sequential.py','sequential_pilot.py','sequential_probes.py','test_sequential.py','Sequential verification design.md','package_sequential.py','verify_sequential_cleanup.py'):
    files['pilot/'+name]=(HERE/name).read_bytes()
files['literature/Sequential verification novelty update.md']=(ROOT/'literature/challenge-monitoring/Sequential verification novelty update.md').read_bytes()
files['licenses/DeathStarBench-LICENSE']=(ROOT/'data/DeathStarBench-LICENSE').read_bytes()
files['README.txt']=(
    'Research development evidence, not a final manuscript.\n'
    '18 historical trials support a post-hoc exhaustive subset replay; 12 new trials compare full and early-stop checking.\n'
    f'From extracted root: python pilot/analyze_sequential.py pilot/sequential-runs/{batch_id}\n'
    'From extracted root: python pilot/replay_refresh.py\n'
    'Both commands use only the Python standard library and do not launch Docker.\n'
    'Verify payload SHA256 hashes against MANIFEST.json.\n'
    'Local source paths and synthetic data are retained. Docker images and mounted benchmark assets are not included.\n'
    'Live deployment needs separately pinned images and runtime files plus bind-path adaptation.\n'
    'The early-stop experiment plan and collector were frozen before launch; its analysis code was written while the batch was running.\n'
    'Replay policies were written after historical outcomes. No public preregistration, powered comparison or novelty proof.\n'
).encode()
manifest={k:hashlib.sha256(v).hexdigest() for k,v in sorted(files.items())}
archive=ROOT/'Sequential-verification-evidence-v0.1.zip'
assert not archive.exists(), 'Keep prior bundles immutable; use a new version'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in sorted(files.items()):z.writestr(name,data)
    z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
destination=HERE/'archive-replay'/('sequential-'+uuid.uuid4().hex)
destination.mkdir(parents=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(n)).hexdigest()==sha for n,sha in manifest.items())
    for name in z.namelist():
        assert (destination/name).resolve().is_relative_to(destination.resolve())
    z.extractall(destination)
outputs=[f'pilot/sequential-runs/{batch_id}/analysis.json',f'pilot/sequential-runs/{batch_id}/Results.md','pilot/refresh-replay/analysis.json','pilot/refresh-replay/Results.md']
before={n:(destination/n).read_bytes() for n in outputs}
for args in (['pilot/analyze_sequential.py',f'pilot/sequential-runs/{batch_id}'],['pilot/replay_refresh.py']):
    p=subprocess.run([sys.executable,'-X','utf8',*args],cwd=destination,capture_output=True,text=True,timeout=60)
    assert p.returncode==0,p.stdout+p.stderr
assert all((destination/n).read_bytes()==v for n,v in before.items())
result={'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
    'payload_files':len(files),'bytes':archive.stat().st_size,'manifest_verified':True,
    'isolated_replay_identical':True,'replay_directory':str(destination)}
(batch/'archive-replay-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
