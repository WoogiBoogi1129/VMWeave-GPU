#!/usr/bin/env python3
"""Verify the built DRA image without requiring a GPU or privileged container."""
import argparse
import hashlib
import mmap
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--engine', choices=['docker', 'podman'], default='docker')
p.add_argument('--image', required=True)
a = p.parse_args()

def run(*args):
    return subprocess.check_output([a.engine, *args], text=True)

version = run('run', '--rm', '--entrypoint', '/usr/bin/hami-kubelet-plugin', a.image, '--version')
assert '0.1.1' in version, version
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    library = root / 'libvgpu.so'
    library.write_bytes(b'old mapped library\n' * 1024)
    with library.open('rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            old, inode = mapped[:], library.stat().st_ino
            run('run', '--rm', '-v', str(root) + ':/target', '--entrypoint', '/bin/bash',
                a.image, '/usr/bin/vgpu-init.sh', '/target')
            assert library.stat().st_ino != inode
            assert mapped[:] == old, 'initializer corrupted an existing mapping'
    actual = hashlib.sha256(library.read_bytes()).hexdigest()
    expected = run('run', '--rm', '--entrypoint', '/bin/bash', a.image,
                   '-c', 'sha256sum /usr/local/lib/hami/libvgpu.so').split()[0]
    assert actual == expected
    assert (root / 'ld.so.preload').read_text().strip() == '/usr/local/vgpu/libvgpu.so'
print('PASS: DRA binary starts, patched library installs, existing mmap survives replacement')
