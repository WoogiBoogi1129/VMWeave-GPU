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


class Publisher:
    def __init__(self, path, transport, library, layout, socket_path):
        self.path = Path(path)
        self.transport = transport
        self.socket_path = Path(socket_path)
        data = Path(layout).read_bytes()
        if len(data) < 64 or struct.unpack_from('<I', data, 40)[0] != 1:
            raise ValueError('plugin discovery requires one layout slot')
        self.identity = {
            'schemaVersion': 1, 'brokerProtocol': 1,
            'allocation': data[:16].hex(), 'generation': data[16:32].hex(),
            'bootID': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'librarySHA256': hashlib.sha256(Path(library).read_bytes()).hexdigest(),
            'maxClients': 1,
        }
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
