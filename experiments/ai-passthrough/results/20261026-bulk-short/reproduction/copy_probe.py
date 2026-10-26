import ctypes as C,json,time,statistics,resource,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args()
x=C.CDLL('/opt/vmweave/lib/libvmweave_guest.so');P=C.c_void_p
for name,args in [('cudaMalloc',[C.POINTER(P),C.c_size_t]),('cudaFree',[P]),('cudaMemcpy',[P,P,C.c_size_t,C.c_int]),('cudaDeviceSynchronize',[])]:f=getattr(x,name);f.argtypes=args;f.restype=C.c_int
sizes=[16777216] if a.diagnostic else [4096,65536,1048575,1048576,1048577,16777216,134217729];maximum=max(sizes);src=C.create_string_buffer(maximum);dst=C.create_string_buffer(maximum);C.memset(src,0x5a,maximum);d=P();other=P();rows=[]
def check(e):
 if e:raise RuntimeError(e)
check(x.cudaMalloc(C.byref(d),maximum));check(x.cudaMalloc(C.byref(other),maximum))
try:
 for size in sizes:
  for label,to,fr,kind in [('H2D',d,C.addressof(src),1),('D2D',other,d,3),('D2H',C.addressof(dst),other,2)]:
   if a.diagnostic and label=='D2D':
    # D2H reads d directly in diagnostic, avoiding extra API noise.
    continue
   if a.diagnostic and kind==2:fr=d
   samples=[]
   for i in range(1 if a.diagnostic else 6):
    wall=time.perf_counter();cpu=time.process_time();check(x.cudaMemcpy(to,fr,size,kind));check(x.cudaDeviceSynchronize());samples.append({'warmup':False if a.diagnostic else i==0,'seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu})
   if kind==2:assert C.string_at(dst,size)==b'\x5a'*size
   rows.append({'bytes':size,'direction':label,'samples':samples,'correct':True})
finally:check(x.cudaFree(other));check(x.cudaFree(d))
Path(a.out).write_text(json.dumps(rows,indent=2)+'\n')
