#!/usr/bin/env python3
"""Check current install/run examples against CLI help and resource ownership."""
from pathlib import Path
import re
import shlex
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]

def main():
    pages = [*ROOT.joinpath('docs/getting-started').glob('*.md'),
             *ROOT.joinpath('docs/guides').glob('*.md'),
             ROOT / 'docs/evaluation/new-experiments.md']
    help_flags = {}
    commands = 0
    for page in pages:
        text = page.read_text()
        for block in re.findall(r'```(?:sh|bash)\n(.*?)```', text, re.S):
            if re.search(r'install-control-plane\.py|charts/flyt-control-plane|render-shm\.py|apiVersion:\s*flyt\.dev', block):
                raise SystemExit(f'Legacy installation in current guide: {page}')
            for match in re.finditer(r'python3\s+(scripts/[\w/.-]+\.py)([^\n]*)', block.replace('\\\n', ' ')):
                script, args = match.groups()
                if script not in help_flags:
                    output = subprocess.check_output([sys.executable, str(ROOT/script), '--help'], text=True, cwd=ROOT)
                    help_flags[script] = set(re.findall(r'--[\w-]+', output))
                flags = {x.split('=')[0] for x in shlex.split(args) if x.startswith('--')}
                if flags - help_flags[script]:
                    raise SystemExit(f'Unknown CLI options in {page}: {flags-help_flags[script]}')
                if script == 'scripts/run-evidence-smoke.py' and '--api-group vmweave.io' not in args:
                    raise SystemExit(f'Explicit new API required: {page}')
                commands += 1
    for name, allowed in [('admin', {'PersistentVolume', 'GPUProfile'}),
                          ('user', {'PersistentVolumeClaim', 'VirtualMachine'})]:
        objects = list(yaml.safe_load_all((ROOT/f'deploy/examples/vmweave/{name}.yaml').read_text()))
        if {o['kind'] for o in objects} != allowed:
            raise SystemExit(f'Incorrect resource ownership in {name}.yaml')
    print(f'PASS: {len(pages)} current guides, {commands} CLI examples, administrator/user split')

if __name__ == '__main__':
    main()
