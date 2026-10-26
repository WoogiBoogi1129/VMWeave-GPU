"""Real Unix FD passing + compiled Guest C path against an in-memory Worker."""
import array
import ctypes
import importlib.util
import mmap
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'runtime/shm/control'))
spec = importlib.util.spec_from_file_location('bulk_broker', ROOT/'runtime/shm/control/guest_broker.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class MemoryWorker(b.Transport):
    def __init__(self):
        self.lock = threading.Lock()
        self.failed = False
        self.memory = b''
        self.calls = 0
        self.bulk_calls = 0
    def exchange(self, api, data, capacity):
        if api == b.CALL:
            return self.copy(bytes(data), capacity)
        return 0, b''
    def copy(self, data, capacity):
        self.calls += 1
        kind = struct.unpack_from('<I', data, 24)[0]
        size = struct.unpack_from('<Q', data, 64)[0]
        if kind == 1:
            self.memory = data[72:]
            assert len(self.memory) == size
            return 0, b''
        assert kind == 2 and capacity == size == len(self.memory)
        return 0, self.memory
    def call(self, api, data, size, output, capacity, got):
        self.bulk_calls += 1
        rc, result = self.copy(ctypes.string_at(data, size), capacity)
        if result:
            ctypes.memmove(output, result, len(result))
        got._obj.value = len(result)
        return rc

PROBE = r'''
import ctypes,struct,sys
lib=ctypes.CDLL(sys.argv[1]);call=lib.vmweave_broker_exchange
call.argtypes=[ctypes.c_uint32,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
n=int(sys.argv[2]);data=bytes((i%251 for i in range(n)))
def invoke(payload,cap):
 out=ctypes.create_string_buffer(max(1,cap));got=ctypes.c_size_t()
 rc=call(0x1012,payload,len(payload),out,cap,ctypes.byref(got));assert rc==0,rc
 return out.raw[:got.value]
assert invoke(struct.pack('<IIQQQQQ',1,0,1,0,0,0,n)+data,0)==b''
assert invoke(struct.pack('<IIQQQQQ',2,0,0,0,1,0,n),n)==data
lib.vmweave_broker_close()
'''

class BulkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.lib = str(Path(cls.tmp.name)/'guest.so')
        subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                        '-I',str(ROOT/'runtime/shm/include'),'-I',str(ROOT/'runtime/shm/shm-contract/include'),
                        str(ROOT/'runtime/shm/src/broker_client.c'),'-pthread','-o',cls.lib],check=True)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def roundtrip(self, size, enabled=True, broker_enabled=True):
        worker=MemoryWorker()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'VMWEAVE_BULK_COPY':'1' if broker_enabled else '0'}):
            listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);path=tmp+'/sock';listener.bind(path);listener.listen()
            def serve():
                conn,_=listener.accept();worker.serve(conn)
            t=threading.Thread(target=serve);t.start()
            env=os.environ.copy();env.update(VMWEAVE_BROKER_SOCKET=path,VMWEAVE_BULK_COPY='1' if enabled else '0',VMWEAVE_STATE_CACHE='0')
            try:
                subprocess.run([sys.executable,'-c',PROBE,self.lib,str(size)],env=env,check=True,timeout=20)
            finally:
                t.join(5);listener.close()
            self.assertFalse(t.is_alive());self.assertFalse(worker.failed);self.assertEqual(worker.calls,2)
            self.assertEqual(worker.bulk_calls,2 if enabled and broker_enabled and size>=1024*1024 else 0)
    def test_large_and_boundary(self):
        for size in [1024*1024-1,1024*1024,16*1024*1024]:
            with self.subTest(size=size):self.roundtrip(size)
    def test_disabled_guest(self):self.roundtrip(1024*1024,enabled=False)
    def test_disabled_broker_fallback(self):self.roundtrip(1024*1024,broker_enabled=False)
    def test_disconnected_mapping_not_reused_by_next_session(self):
        worker=MemoryWorker();old=None
        with patch.dict(os.environ,{'VMWEAVE_BULK_COPY':'1'}):
            for iteration in range(2):
                a,c=socket.socketpair();t=threading.Thread(target=worker.serve,args=(c,));t.start()
                a.sendall(b.REQUEST.pack(b.MAGIC,b.BULK_OPEN,0,0))
                msg,anc,_,_=a.recvmsg(16,socket.CMSG_SPACE(4));self.assertEqual(b.RESPONSE.unpack(msg),(b.MAGIC,0,0))
                fds=array.array('i');fds.frombytes(anc[0][2]);fd=fds[0]
                arena=mmap.mmap(fd,2*b.BULK_BYTES);os.close(fd)
                if iteration==0:arena[:4]=b'old!';old=arena
                else:
                    self.assertEqual(arena[:4],bytes(4));old[:4]=b'bad!'
                    self.assertEqual(arena[:4],bytes(4));arena.close()
                a.close();t.join(3);self.assertFalse(t.is_alive());self.assertFalse(worker.lock.locked())
        old.close()

    def test_success_without_fd_fails_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);path=tmp+'/sock';listener.bind(path);listener.listen()
            observed=[]
            def peer():
                conn,_=listener.accept()
                with conn:
                    observed.append(b.REQUEST.unpack(b.receive(conn,24)))
                    conn.sendall(b.RESPONSE.pack(b.MAGIC,0,0))
                    observed.append(conn.recv(1))
            t=threading.Thread(target=peer);t.start()
            code="import ctypes,struct,sys; x=ctypes.CDLL(sys.argv[1]); f=x.vmweave_broker_exchange; f.argtypes=[ctypes.c_uint32,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]; n=1048576; p=struct.pack('<IIQQQQQ',1,0,1,0,0,0,n)+bytes(n); got=ctypes.c_size_t(); assert f(0x1012,p,len(p),None,0,ctypes.byref(got))==999; assert f(0x1012,p,len(p),None,0,ctypes.byref(got))==999"
            env=os.environ.copy();env.update(VMWEAVE_BROKER_SOCKET=path,VMWEAVE_BULK_COPY='1',VMWEAVE_STATE_CACHE='0')
            try:subprocess.run([sys.executable,'-c',code,self.lib],env=env,check=True,timeout=10)
            finally:t.join(3);listener.close()
            self.assertEqual(observed,[(b.MAGIC,b.BULK_OPEN,0,0),b''])

    def test_invalid_metadata_never_reaches_worker(self):
        worker=MemoryWorker()
        arena=mmap.mmap(-1,2*b.BULK_BYTES)
        try:
            for kind,reserved,size,cap in [(3,0,8,0),(1,1,8,0),(1,0,0,0),(2,0,8,7),(1,0,8,8)]:
                data=struct.pack('<IIQQQQQ',kind,reserved,1,0,1,0,size)
                with self.subTest(kind=kind,reserved=reserved,size=size,cap=cap):
                    with self.assertRaises(ValueError):worker.bulk_copy(bytes(16),data,cap,arena)
            self.assertEqual(worker.calls,0)
        finally:arena.close()

    def test_unnegotiated_copy_is_rejected(self):
        worker=MemoryWorker();a,c=socket.socketpair()
        t=threading.Thread(target=worker.serve,args=(c,));t.start()
        a.sendall(b.REQUEST.pack(b.MAGIC,b.BULK_COPY,48,0)+struct.pack('<IIQQQQQ',1,0,1,0,0,0,8))
        self.assertEqual(a.recv(1),b'');a.close();t.join(3)
        self.assertEqual(worker.calls,0);self.assertFalse(worker.lock.locked())

    def test_sealed_fd_and_invalid_descriptor_close_session(self):
        worker=MemoryWorker();a,c=socket.socketpair()
        with patch.dict(os.environ,{'VMWEAVE_BULK_COPY':'1'}):
            t=threading.Thread(target=worker.serve,args=(c,));t.start()
            a.sendall(b.REQUEST.pack(b.MAGIC,b.BULK_OPEN,0,0))
            msg,anc,flags,_=a.recvmsg(16,socket.CMSG_SPACE(4));self.assertEqual(b.RESPONSE.unpack(msg),(b.MAGIC,0,0))
            fds=array.array('i');fds.frombytes(anc[0][2]);fd=fds[0]
            try:
                with self.assertRaises(OSError):os.ftruncate(fd,1)
                arena=mmap.mmap(fd,2*b.BULK_BYTES)
                self.assertEqual(arena[:64],bytes(64));arena.close()
            finally:os.close(fd)
            data=struct.pack('<IIQQQQQ',1,0,1,0,0,0,b.BULK_BYTES+1)
            a.sendall(b.REQUEST.pack(b.MAGIC,b.BULK_COPY,48,0)+data)
            self.assertEqual(a.recv(1),b'');a.close();t.join(3)
        self.assertEqual(worker.calls,0);self.assertFalse(t.is_alive());self.assertFalse(worker.lock.locked())

if __name__=='__main__':unittest.main()
