"""Versioned, atomic, passive discovery for the optional Kubernetes plugin.

No CUDA session is opened. Only the legacy transport needs an idle heartbeat;
its session lock prevents this from racing a client. Native-owner calls remain
on their owning thread. A stalled exchange expires instead of claiming health.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import threading
import time


def read_layout(path):
    """Read the fixed boot binding; transport validates ring geometry itself."""
    data = Path(path).read_bytes()
    if len(data) < 64:
        raise ValueError('truncated layout')
    count = struct.unpack_from('<I', data, 40)[0]
    if count not in (1, 2) or len(data) != 64 + 80 * count:
        raise ValueError('one or two complete layout slots required')
    ids = [data[64 + 80*i:80 + 80*i].hex() for i in range(count)]
    if not any(data[:16]) or not any(data[16:32]) or '0'*32 in ids or len(set(ids)) != count:
        raise ValueError('invalid binding identity')
    return data[:16].hex(), data[16:32].hex(), ids


class Publisher:
    def __init__(self, path, transport, library, layout, socket_path, slot=0):
        self.path = Path(path)
        self.transport = transport
        self.socket_path = Path(socket_path)
        allocation, generation, sessions = read_layout(layout)
        if not 0 <= slot < len(sessions):
            raise ValueError('invalid discovery slot')
        self.identity = {
            'schemaVersion': 1 if len(sessions) == 1 else 2, 'brokerProtocol': 1,
            'allocation': allocation, 'generation': generation,
            'bootID': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'librarySHA256': hashlib.sha256(Path(library).read_bytes()).hexdigest(),
            'maxClients': 1,
        }
        if len(sessions) > 1:
            self.identity.update(slotIndex=slot, slotCount=len(sessions), sessionID=sessions[slot])
        self.stop = threading.Event()
        self.thread = None
        self.path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        self.publish(False, 'starting')

    def publish(self, ready, reason):
        t = self.transport
        record = dict(self.identity, ready=ready, reason=reason,
                      observedAt=time.time(), transportObservedAt=t.last_success,
                      activeClient=t.lock.locked())
        # Private temporary inode, atomic replacement, no partial JSON readers.
        temporary = self.path.with_name(self.path.name + '.' + str(os.getpid()) + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(record, f); f.write('\n'); f.flush()
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def tick(self):
        t = self.transport
        if not t.owner_mode and not t.failed and t.lock.acquire(blocking=False):
            try:
                rc, _ = t.exchange(3, b'', 0)
                if rc: t.failed = True
            except Exception:
                t.failed = True
            finally:
                t.lock.release()
        age = time.time() - t.last_success
        ready = not t.failed and 0 <= age <= 10
        if not self.stop.is_set():
            self.publish(ready, 'ready' if ready else 'transport-unavailable')

    def start(self):
        self.tick()
        def run():
            while not self.stop.wait(1):
                try:
                    self.tick()
                except Exception as error:
                    # Failure to publish expires the last record. Never kill a
                    # running client merely because optional discovery failed.
                    print('discovery publication failed:', type(error).__name__, flush=True)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=2)
        self.publish(False, 'stopped')
