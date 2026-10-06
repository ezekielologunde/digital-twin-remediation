"""Read-only runtime readiness report. Does not launch or alter Docker."""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return {'args': args, 'returncode': p.returncode,
                'stdout': p.stdout.strip(), 'stderr': p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'args': args, 'returncode': None, 'error': str(exc)}

if __name__ == '__main__':
    disk = shutil.disk_usage(HERE)
    engine = command(['docker', 'info', '--format', '{{json .}}'])
    compose = command(['docker', 'compose', '-f', str(HERE / 'compose.pilot.json'), 'config', '--quiet'])
    report = {'checked_utc': datetime.now(timezone.utc).isoformat(),
              'disk_free_gib': round(disk.free / 1024**3, 1),
              'engine_available': engine['returncode'] == 0,
              'compose_valid': compose['returncode'] == 0,
              'checks': [engine, compose],
              'study_status': 'No deployment or intervention results from preflight'}
    (HERE / 'preflight.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, indent=2))
