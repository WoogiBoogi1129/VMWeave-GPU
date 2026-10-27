"""Actual Guest entry points against the externally provisioned test Broker."""
import ctypes as C
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_gpu', ROOT/'source/tests/integration/large_copy_gpu.py')
copy_gpu=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy_gpu)
lib=C.CDLL(str(ROOT/'build/libvmweave_guest.so'))
def bind(name,args):
    f=getattr(lib,name);f.argtypes=args;f.restype=C.c_int;return f
def check(rc):
    if rc:raise RuntimeError(f'CUDA error {rc}')
p=C.c_void_p
alloc=bind('cudaMalloc',[C.POINTER(p),C.c_size_t]);free=bind('cudaFree',[p])
fill=bind('cudaMemset',[p,C.c_int,C.c_size_t]);sync=bind('cudaDeviceSynchronize',[])
copy=bind('cudaMemcpy',[p,p,C.c_size_t,C.c_int])
get=bind('cudaGetLastError',[]);peek=bind('cudaPeekAtLastError',[])
result={'status':'RUNNING','scope':'host-file-backed-SHM-real-CUDA','flags':{k:v for k,v in os.environ.items() if k.startswith('VMWEAVE_') and 'TEST' not in k}}
try:
    # Includes 16 MiB+1 final short chunk, 128 MiB+1, D2D and 140 async enqueues.
    result['copy_cases']=copy_gpu.qualify(lib)
    ptr=p();total=16*1024*1024+33;check(alloc(C.byref(ptr),total))
    out=C.create_string_buffer(total);cases=[]
    try:
        for n in (0,1,255,4096,1048576,16777216,16777217):
            for value in (0,0x5a,-1):
                check(fill(ptr,0xcc,total));check(sync())
                check(fill(p(ptr.value+16),value,n));check(sync())
                check(copy(out,ptr,total,2));raw=out.raw
                assert raw==b'\xcc'*16+bytes([value&255])*n+b'\xcc'*(total-16-n),(n,value)
                cases.append([n,value])
        assert fill(p(ptr.value+total),0,1)==1
        errors=[peek(),get(),peek()]
        result['invalid_memset_last_error']=errors
        # Legacy async-based wrapper does not record this local validation error.
        assert errors==([1,1,0] if os.getenv('VMWEAVE_NATIVE_MEMSET')=='1' else [0,0,0]),errors
        if os.getenv('VMWEAVE_NATIVE_MEMSET')=='1':
            assert fill(p(ptr.value+total),0,1)==1 and peek()==1
            check(fill(ptr,0,1))
            sticky=[peek(),get(),peek()]
            assert sticky==[1,1,0],sticky
            result['error_survives_successful_memset']=sticky
        check(fill(ptr,0,1));check(sync())
    finally:check(free(ptr))
    result['memset_cases']=cases;result['status']='PASS'
finally:
    lib.vmweave_broker_close()
    Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'copies':len(result['copy_cases']),'memsets':len(result['memset_cases'])}),flush=True)
