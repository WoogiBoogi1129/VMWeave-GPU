#!/usr/bin/env python3
"""Real-GPU copy qualification. --worker uses a LOCAL test bridge to the real
session executable (no VM/ivshmem performance claim). Omit it inside a provisioned
VM to use its broker, or select libcudart.so for a native/Passthrough reference.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time


def receive(sock, n):
    chunks = bytearray()
    while len(chunks) < n:
        data = sock.recv(n-len(chunks))
        if not data:
            raise EOFError('Worker/Guest disconnected')
        chunks.extend(data)
    return bytes(chunks)


def bridge(listener, worker, results):
    child = None
    try:
        conn, _ = listener.accept()
        with conn:
            parent, endpoint = socket.socketpair()
            with parent, endpoint:
                worker_env = os.environ.copy()
                if worker_env.get('VMWEAVE_TEST_WORKER_PRELOAD'):
                    worker_env['LD_PRELOAD'] = worker_env['VMWEAVE_TEST_WORKER_PRELOAD']
                child = subprocess.Popen([worker, '--session', str(endpoint.fileno())], pass_fds=[endpoint.fileno()], env=worker_env)
                endpoint.close()
                while True:
                    magic, api, n, cap = struct.unpack('<IIQQ', receive(conn, 24))
                    assert magic == 0x32574D56 and n <= 16781312 and cap <= 16781312
                    data = receive(conn, n)
                    if api == 2:
                        conn.sendall(struct.pack('<IIQ', magic, 0, 0))
                        break
                    parent.sendall(struct.pack('<IIIIQ', api, 0, 0, 0, n)+data)
                    _, transport, domain, rc, size = struct.unpack('<IIIIQ', receive(parent, 24))
                    out = receive(parent, size)
                    assert size <= cap
                    if transport:
                        rc = 801 if transport == 1 else 999
                    if api == 0x1014 and not rc:
                        version, flags, h, d = struct.unpack('<IIQQ', out)
                        # This test bridge has the same bounded buffers; explicitly
                        # identify it in the result instead of claiming a real broker.
                        out = struct.pack('<IIQQ', version, flags | 2, h, d)
                    results['wire_calls'] = results.get('wire_calls', 0)+1
                    results['max_request_bytes'] = max(n, results.get('max_request_bytes', 0))
                    results['max_response_bytes'] = max(size, results.get('max_response_bytes', 0))
                    conn.sendall(struct.pack('<IIQ', magic, rc, len(out))+out)
    except BaseException as error:
        results['error'] = repr(error)
    finally:
        if child:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
            results['worker_exit'] = child.returncode


def qualify(lib):
    def bind(name, args):
        fn = getattr(lib, name); fn.argtypes = args; fn.restype = C.c_int
        return fn
    ptr, size, integer = C.c_void_p, C.c_size_t, C.c_int
    malloc = bind('cudaMalloc', [C.POINTER(ptr), size]); free = bind('cudaFree', [ptr])
    copy = bind('cudaMemcpy', [ptr, ptr, size, integer])
    asynchronous = bind('cudaMemcpyAsync', [ptr, ptr, size, integer, ptr])
    create = bind('cudaStreamCreate', [C.POINTER(ptr)]); destroy = bind('cudaStreamDestroy', [ptr])
    sync = bind('cudaStreamSynchronize', [ptr]); device_sync = bind('cudaDeviceSynchronize', [])
    event_create = bind('cudaEventCreate', [C.POINTER(ptr)]); record = bind('cudaEventRecord', [ptr, ptr])
    event_sync = bind('cudaEventSynchronize', [ptr]); event_destroy = bind('cudaEventDestroy', [ptr])
    def check(rc):
        if rc: raise RuntimeError(f'CUDA error {rc}')
    max_bytes = 128*1024*1024+1
    host = C.create_string_buffer(max_bytes); out = C.create_string_buffer(max_bytes)
    # Nonuniform pattern detects missing/reordered chunks, not just constant fills.
    block = bytes((i*31+i//257)%256 for i in range(65537))
    for offset in range(0, max_bytes, len(block)):
        C.memmove(C.addressof(host)+offset, block, min(len(block), max_bytes-offset))
    a, b, stream, other, event = ptr(), ptr(), ptr(), ptr(), ptr()
    check(malloc(C.byref(a), max_bytes+64)); check(malloc(C.byref(b), max_bytes+64))
    check(create(C.byref(stream))); check(create(C.byref(other))); check(event_create(C.byref(event)))
    rows = []
    try:
        for n in [0,1,16777215,16777216,16777217,16793604,33554432,33554433,max_bytes]:
            for async_mode in (False, True):
                begin = time.perf_counter()
                if async_mode:
                    check(asynchronous(a.value+17, C.addressof(host), n, 1, stream))
                    check(record(event, stream)); check(event_sync(event))
                    check(asynchronous(b.value+23, a.value+17, n, 3, other))
                    check(asynchronous(C.addressof(out), b.value+23, n, 2, other)); check(sync(other))
                else:
                    check(copy(a.value+17, C.addressof(host), n, 1))
                    check(copy(b.value+23, a.value+17, n, 3))
                    check(copy(C.addressof(out), b.value+23, n, 2))
                check(device_sync()); elapsed=time.perf_counter()-begin
                expected=hashlib.sha256(memoryview(host).cast('B')[:n]).hexdigest()
                actual=hashlib.sha256(memoryview(out).cast('B')[:n]).hexdigest()
                assert expected==actual, (n, async_mode)
                rows.append(dict(bytes=n, async_mode=async_mode, roundtrip_seconds=elapsed, sha256=actual))
        # Sustained enqueues exceed both the staging budget and the old slot count.
        for i in range(140):
            check(asynchronous(a.value, C.addressof(host), 1024*1024, 1, stream if i%2 else other))
        check(sync(stream)); check(sync(other)); check(device_sync())
        return rows
    finally:
        check(device_sync()); check(event_destroy(event)); check(destroy(stream)); check(destroy(other)); check(free(a)); check(free(b))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--library',required=True);parser.add_argument('--worker');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();results={'scope':'local-test-bridge' if args.worker else 'externally-provisioned', 'library':args.library}
    with tempfile.TemporaryDirectory(prefix='vmweave-copy-') as directory:
        thread=None
        if args.worker:
            path=directory+'/broker.sock';listener=socket.socket(socket.AF_UNIX);listener.bind(path);listener.listen(1)
            os.environ['VMWEAVE_BROKER_SOCKET']=path;os.environ['VMWEAVE_STATE_CACHE']='0'
            thread=threading.Thread(target=bridge,args=(listener,args.worker,results));thread.start()
        lib=C.CDLL(args.library)
        try:
            results['cases']=qualify(lib);results['status']='PASS'
        finally:
            if args.worker:
                lib.vmweave_broker_close();thread.join(15);listener.close();assert not thread.is_alive()
            args.out.write_text(json.dumps(results,indent=2)+'\n')
        assert 'error' not in results,results
        print(json.dumps({'status':results['status'],'cases':len(results['cases']),'scope':results['scope']}))

if __name__=='__main__':main()
