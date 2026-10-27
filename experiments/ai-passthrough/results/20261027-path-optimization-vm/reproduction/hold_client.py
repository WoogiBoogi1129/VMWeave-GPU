"""Dedicated cache client for disposable VM failure/recovery qualification."""
import ctypes as C,json,time,os
from pathlib import Path
lib=C.CDLL('/opt/vmweave/lib/libvmweave_guest.so');p=C.c_void_p()
lib.cudaMalloc.argtypes=[C.POINTER(C.c_void_p),C.c_size_t]
assert lib.cudaMalloc(C.byref(p),4096)==0
device=C.c_int();assert lib.cudaGetDevice(C.byref(device))==0
Path('/tmp/short/hold-ready.json').write_text(json.dumps({'pid':os.getpid(),'ready':True}))
end=time.monotonic()+30
while time.monotonic()<end:
    rc=lib.cudaGetDevice(C.byref(device))
    if rc:
        print(json.dumps({'status':'EXPECTED_FENCE','error':rc}),flush=True);break
    time.sleep(.01)
else:raise RuntimeError('dead CUDA child did not fence cached client')
