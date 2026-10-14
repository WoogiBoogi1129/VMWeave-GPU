#!/usr/bin/env python3
"""Single transport owner; each local connection owns a fresh CUDA process.

Clients never map BAR memory. Disconnect (including SIGKILL) closes their session.
A busy slot is rejected, not shared. Broken transport requires a new VM runtime.
"""
import argparse
import ctypes
import fcntl
import os
from pathlib import Path
import secrets
import socket
import struct
import threading

MAGIC = 0x32574D56
MAX_BYTES = 16 * 1024 * 1024 + 4096
REQUEST = struct.Struct('<IIQQ')
RESPONSE = struct.Struct('<IIQ')
OPEN, CLOSE, CALL = 4, 5, 6


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
        os.environ.pop('FLYT_BROKER_SOCKET', None)
        self.lib = ctypes.CDLL(library)
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
            while True:
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
                if api < 0x1000:
                    raise ValueError('client cannot send transport controls')
                rc, out = self.exchange(CALL, epoch + struct.pack('<II', api, 0) + data, capacity)
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
    parser.add_argument('--library', default='/opt/flyt/lib/libflyt_guest.so')
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
