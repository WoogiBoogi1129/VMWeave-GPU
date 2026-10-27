#!/usr/bin/env python3
"""Single transport owner; each local connection owns a fresh CUDA process.

Clients never map BAR memory. Disconnect (including SIGKILL) closes their session.
A busy slot is rejected, not shared. Broken transport requires a new VM runtime.
"""
import vmweave_env as env
import argparse
import ctypes
import fcntl
import mmap
import array
import os
from pathlib import Path
import secrets
import select
import time
import socket
import struct
import threading
import queue

MAGIC = 0x32574D56
MAX_BYTES = 16 * 1024 * 1024 + 4096
REQUEST = struct.Struct('<IIQQ')
RESPONSE = struct.Struct('<IIQ')
OPEN, CLOSE, CALL, STATUS = 4, 5, 6, 7
CACHE_OPEN, CACHE_STATUS = 0x7ff0, 0x7ff1
CACHE_VERSION = 1
COPY_LIMITS = 0x1014
BULK_OPEN, BULK_COPY = 0x7ff2, 0x7ff3
BULK_BYTES = 16 * 1024 * 1024
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
    # Defaults also support existing mock subclasses without native initialization.
    owner_mode = False
    reuse = False
    parts = None
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
        self.parts = None
        if os.environ.get('VMWEAVE_BROKER_GATHER') == '1':
            self.parts = getattr(self.lib, 'vmweave_guest_exchange_parts', None)
            if self.parts is not None:
                self.parts.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
                self.parts.restype = ctypes.c_int
        self.owner = None
        self.owner_mode = os.environ.get('VMWEAVE_BROKER_OWNER') == '1'
        self.last_heartbeat = time.monotonic()
        self.limits = getattr(self.lib, 'vmweave_guest_transport_limits', None)
        if self.owner_mode:
            self.init_owner()
        self.lock = threading.Lock()
        self.failed = False
        self.reuse = os.environ.get('VMWEAVE_BROKER_REUSE') == '1'
        self.scratch = {}
        # Starts the persistent transport's HELLO and heartbeat without CUDA work.
        rc, _ = self.exchange(3, b'', 0)
        if rc:
            if self.owner is not None:
                self.owner_close(self.owner)
                self.owner = None
            raise RuntimeError(f'transport initialization failed: {rc}')

    def init_owner(self):
        ctx = ctypes.c_void_p()
        op = self.lib.vmweave_owner_open
        op.argtypes = [ctypes.POINTER(ctypes.c_void_p)]; op.restype = ctypes.c_int
        ex = self.lib.vmweave_owner_exchange
        ex.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                       ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                       ctypes.POINTER(ctypes.c_size_t)]
        ex.restype = ctypes.c_int
        limits = self.lib.vmweave_owner_limits
        limits.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        limits.restype = ctypes.c_int
        close = self.lib.vmweave_owner_close
        close.argtypes = [ctypes.c_void_p]; close.restype = ctypes.c_int
        rc = op(ctypes.byref(ctx))
        if rc: raise RuntimeError('native transport owner initialization failed')
        self.owner = ctx
        self.call = lambda api, data, n, out, cap, got: ex(ctx, api, data, n, None, 0, out, cap, got)
        if self.parts is not None:
            self.parts = lambda api, head, nh, tail, nt, out, cap, got: ex(ctx, api, head, nh, tail, nt, out, cap, got)
        self.limits = lambda request, response: limits(ctx, request, response)
        self.owner_close = close

    def heartbeat(self):
        if self.owner_mode and time.monotonic() - self.last_heartbeat >= 2:
            rc, _ = self.exchange(3, b'', 0)
            if rc:
                self.failed = True
                raise RuntimeError('transport heartbeat failed')
            self.last_heartbeat = time.monotonic()

    def receive(self, conn, count, deadline):
        if not self.owner_mode:
            return receive(conn, count)
        data = bytearray()
        while len(data) < count:
            self.heartbeat()
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('partial packet deadline')
            if not select.select([conn], [], [], min(0.1, remaining))[0]: continue
            chunk = conn.recv(count - len(data))
            if not chunk: raise EOFError()
            data.extend(chunk)
        return bytes(data)

    def buffer(self, name, size):
        if not 0 <= size <= MAX_BYTES + 24:
            raise ValueError('scratch size out of bounds')
        if not self.reuse:
            return ctypes.create_string_buffer(max(1, size))
        old = self.scratch.get(name)
        if old is None or ctypes.sizeof(old) < max(1, size):
            old = ctypes.create_string_buffer(max(1, size))
            self.scratch[name] = old
        return old

    def exchange(self, api, data, capacity):
        out = self.buffer("output", capacity)
        got = ctypes.c_size_t()
        rc = self.call(api, data, len(data), out, capacity, ctypes.byref(got))
        if got.value > capacity:
            raise RuntimeError('invalid transport output length')
        return rc, ctypes.string_at(out, got.value)

    def bulk_copy(self, epoch, data, capacity, arena):
        # All routing metadata is a private socket snapshot, never client-writable.
        if len(data) != 48:
            raise ValueError('invalid bulk descriptor')
        kind, reserved, dh, do, sh, so, size = struct.unpack('<IIQQQQQ', data)
        if reserved or kind not in (1, 2) or not 0 < size <= BULK_BYTES:
            raise ValueError('invalid bulk direction/size')
        if capacity != (size if kind == 2 else 0):
            raise ValueError('invalid bulk capacity')
        prefix = epoch + struct.pack('<II', 0x1012, 0) + data
        # Input data may change concurrently, like application memory in cudaMemcpy;
        # only payload is shared. Gather mode copies payload directly into transport SHM.
        request_size = len(prefix) + (size if kind == 1 and self.parts is None else 0)
        request = self.buffer("request", request_size)
        ctypes.memmove(request, prefix, len(prefix))
        region = (ctypes.c_char * (2 * BULK_BYTES)).from_buffer(arena)
        try:
            if kind == 1 and self.parts is None:
                ctypes.memmove(ctypes.addressof(request) + len(prefix), ctypes.addressof(region), size)
            output = ctypes.c_void_p(ctypes.addressof(region) + BULK_BYTES)
            got = ctypes.c_size_t()
            if self.parts is not None and kind == 1:
                rc = self.parts(CALL, request, len(prefix), ctypes.addressof(region), size,
                                output, capacity, ctypes.byref(got))
            else:
                rc = self.call(CALL, request, request_size, output, capacity, ctypes.byref(got))
            if got.value > capacity or (not rc and got.value != capacity):
                raise RuntimeError('invalid bulk output length')
            return rc, got.value if not rc else 0
        finally:
            del region

    def serve(self, conn):
        owned = self.lock.acquire(blocking=False)
        epoch = secrets.token_bytes(16)
        opened = False
        arena = None
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
                if self.owner_mode:
                    self.heartbeat()
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
                if self.owner_mode and not select.select([conn], [], [], 0.01)[0]:
                    continue
                deadline = time.monotonic() + 30
                magic, api, count, capacity = REQUEST.unpack(self.receive(conn, REQUEST.size, deadline))
                if magic != MAGIC or count > MAX_BYTES or capacity > MAX_BYTES:
                    raise ValueError('invalid broker request')
                data = self.receive(conn, count, deadline)
                if api == 2 and not count:
                    rc, _ = self.exchange(CLOSE, epoch, 0)
                    opened = False
                    if rc:
                        self.failed = True
                    conn.sendall(RESPONSE.pack(MAGIC, rc, 0))
                    return
                if api == BULK_OPEN:
                    if count or capacity or arena is not None:
                        raise ValueError('invalid/repeated bulk negotiation')
                    if os.environ.get('VMWEAVE_BULK_COPY') != '1':
                        conn.sendall(RESPONSE.pack(MAGIC, 801, 0))
                        continue
                    descriptor = os.memfd_create('vmweave-session-copy', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
                    try:
                        os.ftruncate(descriptor, 2 * BULK_BYTES)
                        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS,
                                    fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
                        arena = mmap.mmap(descriptor, 2 * BULK_BYTES)
                        packet = RESPONSE.pack(MAGIC, 0, 0)
                        sent = conn.sendmsg([packet], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor]))])
                        if sent < len(packet):
                            conn.sendall(packet[sent:])
                    finally:
                        os.close(descriptor)
                    continue
                if api == BULK_COPY:
                    if arena is None:
                        raise ValueError('bulk copy without negotiation')
                    rc, produced = self.bulk_copy(epoch, data, capacity, arena)
                    # Output bytes live in the arena, not on the socket.
                    conn.sendall(RESPONSE.pack(MAGIC, rc, produced))
                    continue
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
                    limits = getattr(self, "limits", None)
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
                if arena is not None:
                    arena.close()
                conn.close()
                if owned:
                    getattr(self, "scratch", {}).clear()
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
    if not transport.owner_mode:
        while True:
            conn, _ = listener.accept()
            threading.Thread(target=transport.serve, args=(conn,), daemon=True).start()
    # Only connection admission crosses threads; all transport calls remain here.
    pending = queue.Queue(maxsize=1)
    busy = threading.Lock()
    def accept_clients():
        while True:
            conn, _ = listener.accept()
            conn.settimeout(30)
            if not busy.acquire(blocking=False):
                try: conn.sendall(RESPONSE.pack(MAGIC, 46, 0))
                except OSError: pass
                finally: conn.close()
            else:
                pending.put(conn)
    threading.Thread(target=accept_clients, daemon=True).start()
    try:
        while not transport.failed:
            try: conn = pending.get(timeout=0.1)
            except queue.Empty:
                transport.heartbeat()
                continue
            try: transport.serve(conn)
            finally: busy.release()
    finally:
        listener.close()
        while True:
            try: pending.get_nowait().close()
            except queue.Empty: break
        if transport.owner is not None:
            transport.owner_close(transport.owner)
            transport.owner = None


if __name__ == '__main__':
    main()
