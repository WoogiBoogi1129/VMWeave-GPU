#!/usr/bin/env python3
"""Validate deployment schema mirrors, migrated source paths and site figures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    for filename in ('channel-crds.json', 'flytgpuprofiles.json', 'flytgpurequests.json'):
        left = json.loads((ROOT / 'deploy/shm' / filename).read_text())
        right = json.loads((ROOT / 'charts/flyt-control-plane/crds' / filename).read_text())
        if left != right: raise SystemExit(f'CRD copies disagree: {filename}')
    manifest = ROOT / 'docs/assets/evidence/manifest.json'
    for item in json.loads(manifest.read_text()):
        for field in ('source', 'asset'):
            path = ROOT / item[field]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise SystemExit(f'Figure content changed: {path}')
    for base in ('runtime', 'scripts', 'tests', 'images', '.github'):
        for path in (ROOT / base).rglob('*'):
            if not path.is_file() or (path.suffix not in ('.c','.h','.py','.sh','.yml','.txt','.Containerfile') and path.name != 'Containerfile'): continue
            text = path.read_text()
            for old in ('experiments/' + 'shm-contract', 'experiments/' + 'shm-queue', 'experiments/' + 'cuda-dispatch'):
                if old in text: raise SystemExit(f'Stale build path {old}: {path}')
    print('PASS: CRD copies, migrated code references, evidence figure hashes')

if __name__ == '__main__': main()
