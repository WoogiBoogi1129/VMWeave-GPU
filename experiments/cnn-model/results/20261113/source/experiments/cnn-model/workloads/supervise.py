#!/usr/bin/env python3
"""Preserve child failure, tensor references and loader evidence in Pod logs."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

root = Path('/results')
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
env = dict(os.environ)
env['PYTHONFAULTHANDLER'] = '1'
if env.get('CNN_LOADER_TRACE') == '1':
    env['LD_DEBUG'] = 'bindings'
    env['LD_DEBUG_OUTPUT'] = '/results/loader'
with (root/'stdout.txt').open('w') as out, (root/'stderr.txt').open('w') as err:
    child = subprocess.Popen([sys.executable, '-u', '/work/probe.py', *sys.argv[1:]], stdout=out, stderr=err, env=env)
    try:
        rc = child.wait(timeout=420); timedout = False
    except subprocess.TimeoutExpired:
        child.kill(); rc = child.wait(); timedout = True
print((root/'stdout.txt').read_text(), end='', flush=True)
print((root/'stderr.txt').read_text(), end='', file=sys.stderr, flush=True)
status = dict(returncode=rc, signal=-rc if rc < 0 else None, timeout=timedout)
(root/'exit.json').write_text(json.dumps(status, indent=2)+'\n')
for path in sorted(root.glob('loader.*')):
    data = path.read_bytes()
    selected = '\n'.join(line for line in data.decode(errors='replace').splitlines() if any(key in line for key in ['cudnn', 'cublas', 'vmweave']))+'\n'
    (root/'loader-filtered.txt').write_text(selected)
    (root/(path.name+'.gz')).write_bytes(gzip.compress(data, mtime=0))
    path.unlink()
for path in sorted(root.iterdir()):
    data = path.read_bytes()
    if len(data) > 8*1024*1024: raise RuntimeError('diagnostic artifact exceeds bound: '+path.name)
    print('CNN_ARTIFACT '+json.dumps(dict(name=path.name, sha256=hashlib.sha256(data).hexdigest(), base64=base64.b64encode(data).decode())), flush=True)
print('CNN_EXIT '+json.dumps(status), flush=True)
sys.exit(124 if timedout else (128-rc if rc < 0 else rc))
