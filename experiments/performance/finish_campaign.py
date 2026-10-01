"""Durable post-measurement handoff; publication still requires review."""
import os
import subprocess
import sys
import time
from common import BASE, OUT, ROOT, save

deadline = time.monotonic() + 10800
retry_cleanup = sys.argv[1:] == ['--resume-cleanup']
retry_captures = sys.argv[1:] == ['--resume-captures']
assert not sys.argv[1:] or retry_cleanup or retry_captures
if retry_cleanup:
    assert (OUT / 'monitoring/retained.json').exists()
    assert (OUT / 'cleanup-recovery/manual-finalization-result.json').exists()
if retry_captures:
    assert (OUT / 'final-audit.json').exists()
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
        [os.environ.get('PERF_NODE', 'node'), 'experiments/performance/capture_terminal.cjs', str(OUT), str(BASE)],
        ['python3', 'experiments/performance/report.py', str(OUT)],
    ]
    for index, command in enumerate(commands):
        if retry_cleanup and index == 0:
            continue
        if retry_captures and index < 3:
            continue
        print('POSTPROCESS_START', index, command, time.time(), flush=True)
        suffix = 'capture-retry-' if retry_captures else 'retry-' if retry_cleanup else ''
        with (BASE / f'final-postprocess-{suffix}{index}.txt').open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           check=True, env={**os.environ, 'NODE_PATH': str(ROOT / '.local/evidence-20260924/tools/node_modules')})
        print('POSTPROCESS_COMPLETE', index, time.time(), flush=True)
    save(OUT / 'postprocess-complete.json', {'utc': time.time(), 'cleanup_retry': (OUT/'cleanup-recovery/manual-finalization-result.json').exists(), 'capture_retry': retry_captures, 'status': 'Awaiting report/capture review, bundle hashing and GitHub publication'})
except BaseException as error:
    failure = 'postprocess-capture-retry-failure.json' if retry_captures else 'postprocess-retry-failure.json' if retry_cleanup else 'postprocess-failure.json'
    save(OUT / failure, {'utc': time.time(), 'error': repr(error)})
    raise
