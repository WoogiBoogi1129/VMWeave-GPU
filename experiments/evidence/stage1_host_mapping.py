"""Read only exact-Pod processes and their allocation-specific SHM mappings."""
import json
import re
import sys
from pathlib import Path

worker_uid, launcher_uid, allocation = sys.argv[1:]
assert all(re.fullmatch('[a-f0-9-]{36}', x) for x in (worker_uid, launcher_uid))
assert re.fullmatch('[a-f0-9]{32}', allocation)
rows = []
for p in Path('/proc').iterdir():
    if not p.name.isdigit():
        continue
    try:
        cg = (p/'cgroup').read_text()
        role = next((r for r, uid in [('worker', worker_uid), ('qemu', launcher_uid)]
                     if uid in cg or uid.replace('-', '_') in cg), None)
        if not role:
            continue
        command = (p/'cmdline').read_bytes()
        if (role == 'worker' and b'/opt/flyt/bin/flyt-shm-worker' not in command or
                role == 'qemu' and b'qemu-kvm' not in command):
            continue
        mappings = []
        for line in (p/'maps').read_text().splitlines():
            parts = line.split(maxsplit=5)
            if len(parts) == 6 and allocation in parts[5] and parts[5].endswith('/channel'):
                mappings.append({'address': parts[0], 'permissions': parts[1],
                                 'device': parts[3], 'inode': parts[4], 'path': parts[5]})
        rows.append({'pid': int(p.name), 'role': role, 'cgroup': cg,
                     'pod_uid': worker_uid if role == 'worker' else launcher_uid,
                     'backing_mappings': mappings})
    except (FileNotFoundError, ProcessLookupError):
        continue
print(json.dumps(rows))
