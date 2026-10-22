"""Real broker/client semantics; only Worker CUDA dispatch is faked.

Run standalone or set VMWEAVE_TEST_GUEST_LIBRARY to exercise the full Guest ELF.
Every case runs in a fresh process because session failures are intentionally sticky.
"""
import ctypes as C
import concurrent.futures
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
import test_state_cache as base

ROOT=Path(__file__).resolve().parents[2]

class Worker(base.Worker):
    def __init__(self,case):
        super().__init__('old_worker' if case=='legacy' else 'normal')
        self.math={};self.reject=False
    def exchange(self,api,data,capacity):
        if api==base.broker.CALL:
            op=struct.unpack('<I',data[16:20])[0]
            if 0x3101<=op<=0x3109:
                self.calls.append((api,data));body=data[24:]
                if self.dead:return 999,b''
                if op==0x3105:
                    if len(body)!=12:return 1,b''
                    h,mode=struct.unpack('<QI',body)
                    if self.reject or not h:return 7,b''
                    self.math[h]=mode
                elif op==0x3102:self.math.pop(struct.unpack('<Q',body)[0],None)
                return 0,b''
        return super().exchange(api,data,capacity)

def run(case,library):
    with tempfile.TemporaryDirectory() as td:
        path=td+'/sock';server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        server.bind(path);server.listen();w=Worker(case);connections=[]
        def serve():
            conn,_=server.accept();connections.append(conn);w.serve(conn)
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        os.environ.update(VMWEAVE_BROKER_SOCKET=path,VMWEAVE_STATE_CACHE='0' if case=='state_off' else '1')
        os.environ.pop('VMWEAVE_BLAS_MATH_CACHE',None)
        os.environ['FLYT_BLAS_MATH_CACHE']='1'  # New feature has no legacy alias.
        if case!='default':os.environ['VMWEAVE_BLAS_MATH_CACHE']='0' if case=='disabled' else '1'
        lib=C.CDLL(library);fn=lib.vmweave_broker_exchange
        fn.argtypes=[C.c_uint32,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
        def call(api,payload=b''):
            out=C.create_string_buffer(8);n=C.c_size_t(99)
            rc=fn(api,payload,len(payload),out,8,C.byref(n))
            if api==0x3105:assert n.value==0
            return rc
        def setmode(h,v):return call(0x3105,struct.pack('<QI',h,v))
        def stats():
            out=(C.c_uint64*5)();lib.vmweave_broker_math_cache_stats(out);return list(out)
        assert setmode(1,0)==0 and setmode(1,0)==0
        enabled=case not in ('default','disabled','state_off','legacy')
        assert w.count(0x3105)==(1 if enabled else 2)
        if not enabled:assert stats()[0:3]==[0,0,0]
        elif case=='mutation':
            assert setmode(1,1)==0 and setmode(1,0)==0 and w.math[1]==0
            assert setmode(2,1)==0 and setmode(1,0)==0 and w.math[2]==1
        elif case=='errors':
            w.reject=True
            assert setmode(1,3)==7 and setmode(1,3)==7
            w.reject=False;before=w.count(0x3105)
            assert setmode(1,0)==0 and w.count(0x3105)==before+1
            assert setmode(0,0)==7
        elif case in ('destroy','create','device'):
            op,payload={'destroy':(0x3102,struct.pack('<Q',1)), 'create':(0x3101,b''), 'device':(0x1003,struct.pack('<i',0))}[case]
            assert call(op,payload)==0;before=w.count(0x3105)
            assert setmode(1,0)==0 and w.count(0x3105)==before+1
        elif case=='capacity':
            for h in range(2,65):assert setmode(h,0)==0
            before=w.count(0x3105)
            assert setmode(65,0)==0 and setmode(65,0)==0
            assert w.count(0x3105)==before+2 and stats()[4]==2
            assert setmode(1,1)==0 and setmode(1,1)==0 and w.math[1]==1
        elif case=='threads':
            before=w.count(0x3105)
            with concurrent.futures.ThreadPoolExecutor(8) as pool:
                assert all(rc==0 for rc in pool.map(lambda _:setmode(1,0),range(200)))
            assert w.count(0x3105)==before
            def mutate(h):
                for mode in range(30):assert setmode(h,mode%2)==0
                assert setmode(h,1)==0
            with concurrent.futures.ThreadPoolExecutor(8) as pool:list(pool.map(mutate,range(2,10)))
            assert all(w.math[h]==1 for h in range(2,10))
        elif case=='fork':
            child=os.fork()
            if child==0:os._exit(0 if setmode(1,0)==999 and stats()==[0]*5 else 1)
            assert os.waitpid(child,0)[1]==0
        elif case in ('worker_death','epoch','broker_death'):
            if case=='worker_death':w.dead=True
            elif case=='epoch':w.wrong_epoch=True
            else:connections[0].shutdown(socket.SHUT_RDWR)
            time.sleep(.12);assert setmode(1,0)==999
            w.dead=False;w.wrong_epoch=False
            assert setmode(1,0)==999 and stats()[0]==0
        elif case=='paths':
            setter=lib.cublasSetMathMode;setter.argtypes=[C.c_void_p,C.c_int]
            before=w.count(0x3105)
            assert setter(C.c_void_p(1),0)==0
            dl=C.CDLL(None);dl.dlsym.argtypes=[C.c_void_p,C.c_char_p];dl.dlsym.restype=C.c_void_p
            address=dl.dlsym(lib._handle,b'cublasSetMathMode');assert address
            dynamic=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int)(address)
            assert dynamic(C.c_void_p(1),0)==0 and w.count(0x3105)==before
        lib.vmweave_broker_close();assert setmode(1,0)==999
        thread.join(2);assert not thread.is_alive();server.close()
        print(json.dumps({'case':case,'status':'PASS','stats':stats()}))

class MathCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.lib=os.environ.get('VMWEAVE_TEST_GUEST_LIBRARY')
        if not cls.lib:
            cls.lib=cls.tmp.name+'/broker.so'
            subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'runtime/shm/include'),'-I',str(ROOT/'runtime/shm/shm-contract/include'),str(ROOT/'runtime/shm/src/broker_client.c'),'-pthread','-o',cls.lib],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def case(self,name):
        r=subprocess.run([sys.executable,__file__,'--case',name,self.lib],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
for case in ('default','disabled','state_off','legacy','mutation','errors','destroy','create','device','capacity','threads','fork','worker_death','epoch','broker_death'):
    setattr(MathCacheTests,'test_'+case,lambda self,case=case:self.case(case))
if os.environ.get('VMWEAVE_TEST_GUEST_LIBRARY'):MathCacheTests.test_paths=lambda self:self.case('paths')
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--case':run(sys.argv[2],sys.argv[3])
    else:unittest.main()
