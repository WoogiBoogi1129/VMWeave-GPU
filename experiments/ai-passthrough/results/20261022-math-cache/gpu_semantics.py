"""Actual cuBLAS mode round trips through the Guest, broker and GPU Worker."""
import ctypes as C,json,concurrent.futures,os,sys,time,signal
from pathlib import Path
if os.geteuid()!=0:
 os.execvp('sudo',['sudo','env','VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock','VMWEAVE_STATE_CACHE=1','VMWEAVE_BLAS_MATH_CACHE=1','VMWEAVE_TEST_NOFAULT='+os.environ.get('VMWEAVE_TEST_NOFAULT','0'),'LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs','/opt/torch-venv/bin/python',__file__])
lib=C.CDLL('/tmp/perf/candidate.so')
create=lib.cublasCreate_v2;create.argtypes=[C.POINTER(C.c_void_p)]
destroy=lib.cublasDestroy_v2;destroy.argtypes=[C.c_void_p]
setmode=lib.cublasSetMathMode;setmode.argtypes=[C.c_void_p,C.c_int]
getmode=lib.cublasGetMathMode;getmode.argtypes=[C.c_void_p,C.POINTER(C.c_int)]
def stats():
 a=(C.c_uint64*5)();lib.vmweave_broker_math_cache_stats(a);return list(a)
hs=[C.c_void_p() for _ in range(4)]
for h in hs:assert create(C.byref(h))==0
for h in hs:
 for mode in [0,2,0]:
  assert setmode(h,mode)==0
  before=stats();assert setmode(h,mode)==0;assert stats()[1]==before[1]+1
  result=C.c_int(-1);assert getmode(h,C.byref(result))==0 and result.value==mode
# Dynamic lookup reaches the same cached entry.
dl=C.CDLL(None);dl.dlsym.argtypes=[C.c_void_p,C.c_char_p];dl.dlsym.restype=C.c_void_p
f=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int)(dl.dlsym(lib._handle,b'cublasSetMathMode'))
before=stats();assert f(hs[0],0)==0 and stats()[1]==before[1]+1
# Invalid enums are sent to cuBLAS, rejected, and never remembered.
rc=[setmode(hs[0],0x7fffffff) for _ in range(2)];assert all(rc)
before=stats();assert setmode(hs[0],0)==0 and stats()[2]==before[2]+1
# Same-handle hits and different-handle changes are serialized by the real client.
def change(h):
 for m in [2,0]*10:assert setmode(h,m)==0
with concurrent.futures.ThreadPoolExecutor(4) as pool:list(pool.map(change,hs))
for h in hs:
 result=C.c_int(-1);assert getmode(h,C.byref(result))==0 and result.value==0
for h in hs:assert destroy(h)==0
h=C.c_void_p();assert create(C.byref(h))==0
before=stats();assert setmode(h,0)==0 and stats()[2]==before[2]+1
assert destroy(h)==0
if os.environ.get('VMWEAVE_TEST_NOFAULT')=='1':
 print(json.dumps({'status':'PASS','scope':'Fresh transport after prior broker death','invalid_enum_results':rc,'stats':stats()}))
 lib.vmweave_broker_close();raise SystemExit
# First invocation kills only this session's Worker child. Second proves fresh
# process recovery, then kills the canary broker and checks cached setters fail.
marker=Path('/tmp/perf/math-worker-fault-ready')
h=C.c_void_p();assert create(C.byref(h))==0
assert setmode(h,0)==0 and setmode(h,0)==0
if not marker.exists():
 fault='worker-child';marker.touch();end=time.monotonic()+120
 while not Path('/tmp/perf/math-worker-fault-done').exists():
  assert time.monotonic()<end,'Worker fault coordinator timed out';time.sleep(.1)
else:
 fault='broker';pid=int(Path('/tmp/perf/broker-profile.pid').read_text())
 assert b'/tmp/perf/broker_profile.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
 os.kill(pid,signal.SIGKILL)
time.sleep(.12)
fault_rc=[setmode(h,0),setmode(h,0)];assert all(fault_rc) and stats()[0]==0
print(json.dumps({'status':'PASS','cases':['multi-handle','modes-0-2','duplicates','dlsym','invalid-enum','threads','destroy-create'],'invalid_enum_results':rc,'fault':fault,'fault_results':fault_rc,'stats':stats()}))
lib.vmweave_broker_close()
