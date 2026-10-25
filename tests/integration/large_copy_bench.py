#!/usr/bin/env python3
"""Diagnostic completed-copy latency; explicit library and provisioned backend.
Not a model throughput benchmark. Reports Guest process CPU/RSS, not Worker RSS.
"""
import argparse,ctypes as C,json,resource,statistics,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--max-bytes',type=int,default=134217729);a=p.parse_args()
x=C.CDLL(a.library);ptr=C.c_void_p
for name,args in [('cudaMalloc',[C.POINTER(ptr),C.c_size_t]),('cudaFree',[ptr]),('cudaMemcpy',[ptr,ptr,C.c_size_t,C.c_int]),('cudaDeviceSynchronize',[])]:
 f=getattr(x,name);f.argtypes=args;f.restype=C.c_int

def check(rc):
 if rc:raise RuntimeError(rc)
n=a.max_bytes;host=C.create_string_buffer(n);out=C.create_string_buffer(n);d=ptr();other=ptr()
check(x.cudaMalloc(C.byref(d),n));check(x.cudaMalloc(C.byref(other),n));C.memset(host,0x5a,n);rows=[]
try:
 for size in [v for v in [4096,16777216,134217729] if v<=n]:
  for label,dst,src,kind in [('H2D',d,C.addressof(host),1),('D2D',other,d,3),('D2H',C.addressof(out),other,2)]:
   for _ in range(3):check(x.cudaMemcpy(dst,src,size,kind));check(x.cudaDeviceSynchronize())
   times=[];cpu=time.process_time()
   for _ in range(20):
    start=time.perf_counter();check(x.cudaMemcpy(dst,src,size,kind));check(x.cudaDeviceSynchronize());times.append(time.perf_counter()-start)
   rows.append(dict(bytes=size,direction=label,median_seconds=statistics.median(times),samples_seconds=times,cpu_seconds=time.process_time()-cpu,guest_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
finally:
 check(x.cudaFree(d));check(x.cudaFree(other))
a.out.write_text(json.dumps(rows,indent=2)+'\n')
