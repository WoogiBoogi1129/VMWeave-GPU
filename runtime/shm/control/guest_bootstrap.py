#!/usr/bin/env python3
"""Prepare one boot binding and run fixed, independent broker owners."""
import base64
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import vmweave_env as env
from guest_status import read_layout


def run_brokers(count, environ, root=Path('/run/vmweave'),
                status_root=Path('/run/vmweave-device-plugin'),
                broker='/opt/vmweave/control/guest_broker.py'):
    """No restart on consumed rings. A failed child does not kill its peers."""
    if count not in (1, 2):
        raise ValueError('one or two brokers required')
    children = []
    stopping = False
    def stop(*args):
        nonlocal stopping
        stopping = True
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        root.mkdir(mode=0o750, exist_ok=True)
        status_root.mkdir(mode=0o755, exist_ok=True)
        if count > 1:
            (root/'slots').mkdir(mode=0o750, exist_ok=True)
            (status_root/'slots').mkdir(mode=0o755, exist_ok=True)
        for slot in range(count):
            directory = root if count == 1 else root / 'slots' / str(slot)
            state = status_root if count == 1 else status_root / 'slots' / str(slot)
            directory.mkdir(mode=0o750, parents=True, exist_ok=True)
            child_env = dict(environ, VMWEAVE_SLOT=str(slot))
            children.append(subprocess.Popen(
                [sys.executable, broker, '--socket', str(directory/'gpu.sock'),
                 '--status', str(state/'status.json')], env=child_env))
        while not stopping and any(p.poll() is None for p in children):
            time.sleep(0.1)
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        deadline = time.monotonic() + 15
        for p in children:
            try:
                p.wait(timeout=max(0.01, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0 if stopping or all(p.returncode == 0 for p in children) else 1


def main():
    mount = Path('/run/vmweave-config')
    mount.mkdir(exist_ok=True)
    subprocess.run(['mount', '-o', 'ro', '/dev/disk/by-label/cidata', str(mount)], check=True)
    try:
        data = (mount/'user-data').read_text()
    finally:
        subprocess.run(['umount', str(mount)], check=True)
    lines = [line.split(':', 1)[1].strip() for line in data.splitlines()
             if line.startswith('# vmweave-layout-b64:')]
    if len(lines) != 1:
        raise RuntimeError('one authoritative VMWeave boot layout required')
    if int(env.get('VMWEAVE_SLOT', '0')) != 0:
        raise RuntimeError('bootstrap selects slots from the boot layout')
    root = Path('/run/vmweave')
    root.mkdir(mode=0o750, exist_ok=True)
    layout = root/'layout.bin'
    lock = open(root/'bootstrap.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    marker = root/'boot-started'
    if marker.exists():
        raise RuntimeError('broker binding already started; fresh VM boot required')
    temporary = root/'layout.new'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(base64.b64decode(lines[0], validate=True))
        _, _, sessions = read_layout(temporary)
        devices = [p for p in Path('/sys/bus/pci/devices').iterdir()
                   if (p/'vendor').read_text().strip() == '0x1af4'
                   and (p/'device').read_text().strip() == '0x1110']
        if len(devices) != 1:
            raise RuntimeError('exactly one ivshmem device required')
        os.replace(temporary, layout)
    finally:
        temporary.unlink(missing_ok=True)
    marker.touch(exist_ok=False)
    child_env = dict(os.environ, VMWEAVE_LAYOUT=str(layout), VMWEAVE_IVSHMEM_BDF=devices[0].name)
    return run_brokers(len(sessions), child_env)


if __name__ == '__main__':
    raise SystemExit(main())
