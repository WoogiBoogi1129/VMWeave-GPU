"""Real C client + production Python broker; fake only the remote Worker.

No GPU required. Each subprocess owns a fresh client session. Set
VMWEAVE_TEST_GUEST_LIBRARY to the built Guest ELF to also test CUDA entry paths.
"""
import ctypes as C
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/shm/control'))
spec = importlib.util.spec_from_file_location('broker', ROOT/'runtime/shm/control/guest_broker.py')
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)

class Worker(broker.Transport):
    def __init__(self, case):
        self.lock = threading.Lock()
        self.failed = False
        self.case = case
        self.dead = False
        self.active = 1
        self.flags = 8 if case == 'fresh_flags' else 0
        self.wrong_epoch = False
        self.calls = []
        self.epochs = []
        self.hold_health = False
        self.health_entered = threading.Event()
        self.release_health = threading.Event()
    def exchange(self, api, data, capacity):
        self.calls.append((api, data))
        if api == broker.OPEN:
            self.epochs.append(data)
            return 0, b''
        if api == broker.CLOSE:
            return 0, b''
        if api == broker.STATUS:
            if self.hold_health:
                self.health_entered.set()
                assert self.release_health.wait(3)
            if self.case == 'old_worker' or self.dead:
                return 999, b''
            return 0, b'x'*16 if self.wrong_epoch else data
        assert api == broker.CALL
        operation, _ = struct.unpack('<II', data[16:24])
        if self.dead:
            return 999, b''
        if operation == 0x1001:
            return 0, struct.pack('<i', 2 if self.case == 'multi_gpu' else 1)
        if operation == 0x1002:
            return 0, struct.pack('<i', 0)
        if operation == 0x2107:
            return 0, struct.pack('<Ii', self.flags, self.active)
        if operation == 0x1003:
            self.flags = 8  # Make invalidation observable, not just a counter.
            return 0, b''
        return 1, b''
    def count(self, api):
        return sum(a == broker.CALL and struct.unpack('<I', d[16:20])[0] == api for a,d in self.calls)


def client_case(case, library):
    with tempfile.TemporaryDirectory() as directory:
        path = directory+'/broker.sock'
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen()
        worker = Worker(case)
        servers = []
        def serve():
            conn, _ = listener.accept()
            servers.append(conn)
            if case in ('old_broker','malformed_capability'):
                # Previous framing: unknown API is forwarded as unsupported.
                try:
                    while True:
                        magic, api, count, capacity = broker.REQUEST.unpack(broker.receive(conn,24))
                        data = broker.receive(conn,count)
                        rc,out = (0, b'') if api == 2 or (case == 'malformed_capability' and api == broker.CACHE_OPEN) else (801,b'') if api == broker.CACHE_OPEN else worker.exchange(broker.CALL, b'\0'*16+struct.pack('<II',api,0)+data, capacity)
                        conn.sendall(broker.RESPONSE.pack(magic,rc,len(out))+out)
                        if api == 2:break
                except EOFError:pass
                finally:conn.close()
            else:
                worker.serve(conn)
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        os.environ['VMWEAVE_BROKER_SOCKET'] = path
        os.environ['VMWEAVE_STATE_CACHE'] = '0' if case in ('disabled','disabled_error') else '1'
        lib = C.CDLL(library)
        exchange = lib.vmweave_broker_exchange
        exchange.argtypes = [C.c_uint32,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
        exchange.restype = C.c_int
        def query(api=0x1002, payload=b'', capacity=8):
            out = C.create_string_buffer(capacity)
            got = C.c_size_t()
            rc = exchange(api,payload,len(payload),out,capacity,C.byref(got))
            return rc, out.raw[:got.value]
        def stats():
            a = (C.c_uint64*6)();lib.vmweave_broker_cache_stats(a);return list(a)
        assert query() == (0, b'\0'*4)
        assert query() == (0, b'\0'*4)
        enabled = case not in ('disabled','disabled_error','old_worker','old_broker','multi_gpu','malformed_capability')
        assert bool(stats()[0]) == enabled
        assert worker.count(0x1002) == (1 if enabled else 2)
        if case == 'paths':
            if not hasattr(lib,'cuDevicePrimaryCtxGetState'):
                raise AssertionError('paths requires built Guest ELF')
            # A specific handle, global symbol, then cuGetProcAddress function.
            global_lib = C.CDLL(None)
            def context(fn):
                flags,active = C.c_uint(),C.c_int()
                assert fn(0,C.byref(flags),C.byref(active)) == 0
                assert (flags.value,active.value) == (0,1)
            context(global_lib.cuDevicePrimaryCtxGetState)
            context(lib.cuDevicePrimaryCtxGetState)
            ptr = C.c_void_p()
            proc = lib.cuGetProcAddress
            proc.argtypes=[C.c_char_p,C.POINTER(C.c_void_p),C.c_int,C.c_uint64]
            assert proc(b'cuDevicePrimaryCtxGetState',C.byref(ptr),12000,0)==0
            context(C.CFUNCTYPE(C.c_int,C.c_int,C.c_void_p,C.c_void_p)(ptr.value))
            assert worker.count(0x2107)==1
            assert lib.cuDevicePrimaryCtxGetState(1,None,None)!=0
            assert lib.cudaGetDevice(None)==1
        elif case == 'inactive':
            worker.active=0
            assert query(0x2107)==(0,b'\0'*8)
            assert query(0x2107)==(0,b'\0'*8)
            assert worker.count(0x2107)==2
            worker.active=1
            query(0x2107);query(0x2107)
            assert worker.count(0x2107)==3
        elif case == 'state_change':
            query(0x2107)
            assert query(0x1003,struct.pack('<i',0))[0]==0
            assert query(0x2107)==(0,struct.pack('<Ii',8,1))
            assert worker.count(0x2107)==2
        elif case == 'nonfatal_error':
            assert query(0x7777)[0]==1
            assert query()[0]==0
            assert worker.count(0x1002)==2
        elif case == 'disabled_error':
            worker.dead=True
            assert query(0x7777)[0]==999
            worker.dead=False
            assert query()[0]==0
        elif case == 'fatal_error':
            worker.dead=True
            assert query(0x7777)[0]==999
            assert query()[0]==999
        elif case == 'fork':
            pid=os.fork()
            if pid==0:os._exit(0 if query()[0]==999 else 1)
            assert os.waitpid(pid,0)[1]==0
            assert query()[0]==0
        elif case == 'fresh_flags':
            assert query(0x2107)==(0,struct.pack('<Ii',8,1))
            assert query(0x2107)==(0,struct.pack('<Ii',8,1))
            assert worker.count(0x2107)==1
        elif case in ('worker_death','broker_death','epoch_change'):
            if case=='worker_death':worker.dead=True
            elif case=='epoch_change':worker.wrong_epoch=True
            else:servers[0].shutdown(socket.SHUT_RDWR)
            deadline=time.monotonic()+1
            while query()[0]==0:
                assert time.monotonic()<deadline
                time.sleep(.002)
            assert query()[0]==999
        elif case == 'lease':
            worker.hold_health=True
            assert worker.health_entered.wait(1)
            time.sleep(.06)
            result=[]
            caller=threading.Thread(target=lambda:result.append(query()))
            caller.start()
            time.sleep(.02)
            assert caller.is_alive(), 'expired cache returned success without health response'
            worker.dead=True
            worker.release_health.set()
            caller.join(2)
            assert result and result[0][0]==999
        elif case == 'threads':
            errors=[]
            def many():
                for _ in range(200):
                    if query()!=(0,b'\0'*4):errors.append('bad value')
            threads=[threading.Thread(target=many) for _ in range(8)]
            for t in threads:t.start()
            for t in threads:t.join(2);assert not t.is_alive()
            assert not errors and worker.count(0x1002)==1
        elif case == 'close_race':
            results=[]
            callers=[threading.Thread(target=lambda:results.extend(query()[0] for _ in range(100))) for _ in range(4)]
            for t in callers:t.start()
            lib.vmweave_broker_close()
            for t in callers:t.join(2);assert not t.is_alive()
            assert results and all(rc in (0,999) for rc in results)
            assert query()[0]==999
        elif case == 'bad_arguments':
            got=C.c_size_t(10)
            assert exchange(0x1002,None,0,None,4,C.byref(got))==1
            assert got.value==0
            assert query()[0]==0
        lib.vmweave_broker_close()
        assert query()[0]==999
        thread.join(2)
        assert not thread.is_alive()
        listener.close()
        print(json.dumps({'case':case,'status':'PASS','stats':stats()}))

class StateCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.library=os.environ.get('VMWEAVE_TEST_GUEST_LIBRARY')
        if not cls.library:
            cls.library=cls.tmp.name+'/broker.so'
            subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'runtime/shm/include'),'-I',str(ROOT/'runtime/shm/shm-contract/include'),str(ROOT/'runtime/shm/src/broker_client.c'),'-pthread','-o',cls.library],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_case(self,case):
        env={**os.environ}
        if case=='paths':env['LD_PRELOAD']=self.library
        result=subprocess.run([sys.executable,__file__,'--case',case,self.library],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

for case in ('disabled','disabled_error','old_worker','old_broker','multi_gpu','inactive','state_change','nonfatal_error','fatal_error','fork','worker_death','broker_death','lease','threads','bad_arguments','fresh_flags','epoch_change','close_race','malformed_capability'):
    setattr(StateCacheTests,'test_'+case,lambda self,case=case:self.run_case(case))
if os.environ.get('VMWEAVE_TEST_GUEST_LIBRARY'):
    StateCacheTests.test_paths=lambda self:self.run_case('paths')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--case':client_case(sys.argv[2],sys.argv[3])
    else:unittest.main()
