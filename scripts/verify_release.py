"""Verify frozen evidence and replay analyses without modifying the checkout."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    ("direct", "direct-runs/3049d39ca8b942858f518d4b5b2317b1"),
    ("sequential", "sequential-runs/5f71ebb803bd4d939e978b6e80eeecf5"),
    ("temporal", "temporal-runs/294bab8ce4274cb7b50c52b48b59c78b"),
    ("race", "race-runs/9494250949eb49d5a9bb33a82bc00d5d"),
    ("aligned_event", "aligned-event-runs/fc54dc7bbf804c07b54d357033a60c70"),
]

def run(args, cwd):
    subprocess.run([sys.executable, "-X", "utf8", *args], cwd=cwd, check=True, timeout=120)

def main():
    manifest = json.loads((ROOT / "MANIFEST.json").read_text())
    for name, expected in manifest.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Evidence integrity failure: " + name)
    print(f"Verified {len(manifest)} original payload hashes.", flush=True)
    run(["-m", "unittest", "discover", "-s", "pilot", "-p", "test_*.py"], ROOT)
    with tempfile.TemporaryDirectory(prefix="remediation-replay-") as tmp:
        dest = Path(tmp)
        for folder in ("pilot", "publication", "overleaf"):
            shutil.copytree(ROOT / folder, dest / folder, ignore=shutil.ignore_patterns("__pycache__"))
        outputs = [f"pilot/{batch}/{name}" for _, batch in STAGES for name in ("analysis.json", "Results.md")]
        outputs += ["overleaf/main.tex", "publication/manuscript-provenance.json"]
        before = {name: (dest / name).read_bytes() for name in outputs}
        for method, batch in STAGES:
            argument = batch.split("/")[1] if method == "direct" else "pilot/" + batch
            run([f"pilot/analyze_{method}.py", argument], dest)
        run(["publication/build_manuscript.py"], dest)
        for name, expected in before.items():
            if (dest / name).read_bytes() != expected:
                raise RuntimeError("Replay changed output: " + name)
    print("PASS: 40 tests, five analyses and manuscript reproduced exactly. PDF compilation not checked.")

if __name__ == "__main__":
    main()
