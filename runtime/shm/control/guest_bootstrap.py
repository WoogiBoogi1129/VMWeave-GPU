#!/usr/bin/env python3
"""Load this boot's layout from the KubeVirt config drive, not cloud-init cache."""
import vmweave_env as env
import base64
import os
from pathlib import Path
import subprocess
import sys

mount = Path('/run/vmweave-config')
mount.mkdir(exist_ok=True)
subprocess.run(['mount', '-o', 'ro', '/dev/disk/by-label/cidata', str(mount)], check=True)
try:
    data = (mount / 'user-data').read_text()
finally:
    subprocess.run(['umount', str(mount)], check=True)
lines = [line.split(':', 1)[1].strip() for line in data.splitlines()
         if line.startswith('# vmweave-layout-b64:')]
if len(lines) != 1:
    raise RuntimeError('one authoritative VMWeave boot layout required')
layout = base64.b64decode(lines[0], validate=True)
Path('/run/vmweave').mkdir(mode=0o750, exist_ok=True)
Path('/run/vmweave/layout.bin').write_bytes(layout)
os.environ['VMWEAVE_LAYOUT'] = '/run/vmweave/layout.bin'
if int(env.get('VMWEAVE_SLOT', '0')) != 0:
    raise RuntimeError('guest broker currently supports slot 0 only')
os.environ['VMWEAVE_SLOT'] = '0'
devices = [p for p in Path('/sys/bus/pci/devices').iterdir()
           if (p/'vendor').read_text().strip() == '0x1af4' and (p/'device').read_text().strip() == '0x1110']
if len(devices) != 1:
    raise RuntimeError('exactly one ivshmem device required')
os.environ['VMWEAVE_IVSHMEM_BDF'] = devices[0].name
os.execv(sys.executable, [sys.executable, '/opt/vmweave/control/guest_broker.py'])
