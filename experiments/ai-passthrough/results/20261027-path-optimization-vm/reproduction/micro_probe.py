import argparse,ctypes as C,json,time,hashlib,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--out',required=True);a=p.parse_args()
x=C.CDLL(a.library);P=C.c_void_p
for name,args in [('cudaMalloc',[C.POINTER(P),C.c_size_t]),('cudaFree',[P]),('cudaMemcpy',[P,P,C.c_size_t,C.c_int]),('cudaMemset',[P,C.c_int,C.c_size_t]),('cudaDeviceSynchronize',[])]:
 f=getattr(x,name);f.argtypes=args;f.restype=C.c_int
def check(e):
 if e:raise RuntimeError(e)
sizes=[4096,65536,1048575,1048576,1048577,16777216,134217729]
n=max(sizes);src=C.create_string_buffer(n);dst=C.create_string_buffer(n);d=P();other=P();rows=[]
block=bytes((i*31+i//257)%256 for i in range(65537))
for offset in range(0,n,len(block)):C.memmove(C.addressof(src)+offset,block,min(len(block),n-offset))
check(x.cudaMalloc(C.byref(d),n));check(x.cudaMalloc(C.byref(other),n))
def sample(fn):
 values=[]
 for i in range(6):
  check(x.cudaDeviceSynchronize());cpu=time.process_time_ns();t0=time.perf_counter_ns()
  check(fn());t1=time.perf_counter_ns();check(x.cudaDeviceSynchronize());t2=time.perf_counter_ns()
  values.append({'warmup':i==0,'api_ns':t1-t0,'completion_ns':t2-t0,'caller_cpu_ns':time.process_time_ns()-cpu})
 return values
try:
 for size in sizes:
  for label,to,fr,kind in [('H2D',d,C.addressof(src),1),('D2D',other,d,3),('D2H',C.addressof(dst),other,2)]:
   samples=sample(lambda:x.cudaMemcpy(to,fr,size,kind))
   # Validation outside timing, for every direction independently.
   if kind!=2:check(x.cudaMemcpy(dst,to,size,2))
   assert C.string_at(dst,size)==C.string_at(src,size),(label,size)
   rows.append({'operation':label,'bytes':size,'samples':samples,'correct':True})
 for size in [4,4096,1048576,16777216]:
  samples=sample(lambda:x.cudaMemset(d,0x5a,size));check(x.cudaMemcpy(dst,d,size,2))
  assert C.string_at(dst,size)==b'\x5a'*size
  rows.append({'operation':'memset','bytes':size,'samples':samples,'correct':True})
finally:check(x.cudaFree(other));check(x.cudaFree(d))
Path(a.out).write_text(json.dumps({'library':a.library,'rows':rows,'status':'PASS','timing':'caller return and explicit device completion; one warmup excluded'},indent=2)+'\n')
print('PASS',len(rows),'microbenchmark cells',flush=True)
