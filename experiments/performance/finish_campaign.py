"""Durable post-measurement handoff; publication still requires review."""
import os
import subprocess
import time
from common import BASE, OUT, ROOT, save

deadline = time.monotonic() + 10800
try:
    while not (OUT / 'campaign-execution-complete.json').exists():
        if (OUT / 'resume1-failure.json').exists():
            raise RuntimeError('Resumed measurements failed; preserve evidence for review')
        if time.monotonic() >= deadline:
            raise TimeoutError('Measurements did not finish before handoff deadline')
        time.sleep(10)
    commands = [
        ['python3', 'experiments/performance/retain_monitoring.py'],
        ['python3', 'experiments/performance/cleanup.py'],
        ['python3', 'experiments/performance/final_audit.py'],
        ['node', 'experiments/performance/capture_terminal.cjs', str(OUT), str(BASE)],
        ['python3', 'experiments/performance/report.py', str(OUT)],
    ]
    for index, command in enumerate(commands):
        print('POSTPROCESS_START', index, command, time.time(), flush=True)
        with (BASE / f'final-postprocess-{index}.txt').open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           check=True, env={**os.environ, 'NODE_PATH': str(ROOT / '.local/evidence-20260924/tools/node_modules')})
        print('POSTPROCESS_COMPLETE', index, time.time(), flush=True)
    save(OUT / 'postprocess-complete.json', {'utc': time.time(), 'status': 'Awaiting report/capture review, bundle hashing and GitHub publication'})
except BaseException as error:
    save(OUT / 'postprocess-failure.json', {'utc': time.time(), 'error': repr(error)})
    raise
