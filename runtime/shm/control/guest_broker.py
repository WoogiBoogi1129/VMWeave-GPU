#!/usr/bin/env python3
"""Single transport owner; each local connection owns a fresh CUDA process.

Clients never map BAR memory. Disconnect (including SIGKILL) closes their session.
A busy slot is rejected, not shared. Broken transport requires a new VM runtime.
"""
import vmweave_env as env
import argparse
import ctypes
import fcntl
import os
from pathlib import Path
import secrets
import select
import time
import socket
import struct
import threading

MAGIC = 0x32574D56
MAX_BYTES = 16 * 1024 * 1024 + 4096
REQUEST = struct.Struct('<IIQQ')
RESPONSE = struct.Struct('<IIQ')
OPEN, CLOSE, CALL, STATUS = 4, 5, 6, 7
CACHE_OPEN, CACHE_STATUS = 0x7ff0, 0x7ff1
CACHE_VERSION = 1
COPY_LIMITS = 0x1014
HEALTH_INTERVAL = 0.010


def receive(conn, count):
    data = bytearray()
    while len(data) < count:
        part = conn.recv(count - len(data))
        if not part:
            raise EOFError()
        data.extend(part)
    return bytes(data)


class Transport:
    def __init__(self, library):
        # This process is the SHM owner, never a client of its own socket.
        env.pop('VMWEAVE_BROKER_SOCKET')
        self.lib = ctypes.CDLL(library)
        self.call = getattr(self.lib, "vmweave_guest_exchange", None)
        if self.call is None:  # Mixed-version upgrade with an older Guest library.
            self.call = self.lib.flyt_guest_exchange
        self.call.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                              ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.call.restype = ctypes.c_int
        self.lock = threading.Lock()
        self.failed = False
        # Starts the persistent transport's HELLO and heartbeat without CUDA work.
        rc, _ = self.exchange(3, b'', 0)
        if rc:
            raise RuntimeError(f'transport initialization failed: {rc}')

    def exchange(self, api, data, capacity):
        out = ctypes.create_string_buffer(max(1, capacity))
        got = ctypes.c_size_t()
        rc = self.call(api, data, len(data), out, capacity, ctypes.byref(got))
        if got.value > capacity:
            raise RuntimeError('invalid transport output length')
        return rc, out.raw[:got.value]

    def serve(self, conn):
        owned = self.lock.acquire(blocking=False)
        epoch = secrets.token_bytes(16)
        opened = False
        try:
            if not owned or self.failed:
                conn.sendall(RESPONSE.pack(MAGIC, 46, 0))
                return
            rc, _ = self.exchange(OPEN, epoch, 0)
            if rc:
                conn.sendall(RESPONSE.pack(MAGIC, rc, 0))
                return
            opened = True
            cache_enabled = False
            next_health = 0.0
            while True:
                if cache_enabled:
                    now = time.monotonic()
                    if now >= next_health:
                        rc, state = self.exchange(STATUS, epoch, 16)
                        if rc or state != epoch:
                            # EOF/HUP is the notification; never interleave packets
                            # with a synchronous CUDA reply on this byte stream.
                            conn.shutdown(socket.SHUT_RDWR)
                            return
                        next_health = time.monotonic() + HEALTH_INTERVAL
                    if not select.select([conn], [], [], max(0, next_health-time.monotonic()))[0]:
                        continue
                magic, api, count, capacity = REQUEST.unpack(receive(conn, REQUEST.size))
                if magic != MAGIC or count > MAX_BYTES or capacity > MAX_BYTES:
                    raise ValueError('invalid broker request')
                data = receive(conn, count)
                if api == 2 and not count:
                    rc, _ = self.exchange(CLOSE, epoch, 0)
                    opened = False
                    if rc:
                        self.failed = True
                    conn.sendall(RESPONSE.pack(MAGIC, rc, 0))
                    return
                if api in (CACHE_OPEN, CACHE_STATUS):
                    expected = 24 if api == CACHE_OPEN else 16
                    if count or capacity != expected:
                        conn.sendall(RESPONSE.pack(MAGIC, 1, 0))
                        continue
                    rc, state = self.exchange(STATUS, epoch, 16)
                    if rc or state != epoch:
                        if cache_enabled:
                            conn.shutdown(socket.SHUT_RDWR)
                            return
                        # Old Worker does not implement STATUS: ordinary calls
                        # continue, without caching or a change in CUDA state.
                        conn.sendall(RESPONSE.pack(MAGIC, 801, 0))
                        continue
                    if api == CACHE_OPEN:
                        rc, devices = self.exchange(CALL, epoch + struct.pack('<II', 0x1001, 0), 4)
                        if rc or devices != struct.pack('<i', 1):
                            conn.sendall(RESPONSE.pack(MAGIC, 801, 0))
                            continue
                        cache_enabled = True
                        payload = struct.pack('<II', CACHE_VERSION, 1) + epoch
                    else:
                        if not cache_enabled:
                            conn.sendall(RESPONSE.pack(MAGIC, 801, 0))
                            continue
                        payload = epoch
                    next_health = time.monotonic() + HEALTH_INTERVAL
                    conn.sendall(RESPONSE.pack(MAGIC, 0, len(payload)) + payload)
                    continue
                if api < 0x1000:
                    raise ValueError('client cannot send transport controls')
                rc, out = self.exchange(CALL, epoch + struct.pack('<II', api, 0) + data, capacity)
                if api == COPY_LIMITS and not rc:
                    limits = getattr(self.lib, 'vmweave_guest_transport_limits', None)
                    request, response = ctypes.c_size_t(), ctypes.c_size_t()
                    if len(out) != 24 or limits is None or limits(ctypes.byref(request), ctypes.byref(response)):
                        rc, out = 801, b''
                    else:
                        version, flags, upload, download = struct.unpack('<IIQQ', out)
                        # Reserve the 24-byte session envelope and largest copy header.
                        upload = min(upload, MAX_BYTES - 56, request.value - 24 - 56)
                        download = min(download, MAX_BYTES, response.value)
                        if version != 1 or upload <= 0 or download <= 0:
                            rc, out = 801, b''
                        else:
                            out = struct.pack('<IIQQ', version, flags | 2, upload, download)
                conn.sendall(RESPONSE.pack(MAGIC, rc, len(out)) + out)
        except (EOFError, OSError, ValueError, RuntimeError) as error:
            print(f'client disconnected: {type(error).__name__}', flush=True)
        finally:
            try:
                if opened:
                    rc, _ = self.exchange(CLOSE, epoch, 0)
                    if rc:
                        self.failed = True
            except Exception:
                self.failed = True
                raise
            finally:
                conn.close()
                if owned:
                    self.lock.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', default='/opt/vmweave/lib/libvmweave_guest.so')
    parser.add_argument('--socket', default='/run/vmweave/gpu.sock')
    args = parser.parse_args()
    path = Path(args.socket)
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    lock = open(str(path) + '.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    transport = Transport(args.library)
    path.unlink(missing_ok=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    os.chmod(path, 0o660)
    listener.listen(8)
    print('VMWeave broker ready; no active CUDA job', flush=True)
    while True:
        conn, _ = listener.accept()
        threading.Thread(target=transport.serve, args=(conn,), daemon=True).start()


if __name__ == '__main__':
    main()
