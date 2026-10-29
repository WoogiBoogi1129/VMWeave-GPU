"""Identical direct cuBLAS SGEMM, bounded queues, completion-delimited timing."""
import argparse,ctypes as C,hashlib,json,math,os,resource,signal,time
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
CHUNK=1<<20
WORKSPACE=16*1024*1024
BUDGET=int(.8*8*1024**3)

def values(indices,seed,n):
 x=np.asarray(indices,dtype=np.uint32)+np.uint32(seed)
 x=(x^(x>>16))*np.uint32(0x7feb352d);x=(x^(x>>15))*np.uint32(0x846ca68b);x=x^(x>>16)
 return ((x&np.uint32(65535)).astype(np.float32)-np.float32(32768))*np.float32(1/32768)*np.float32(n**-.25)

def metrics(n,count,elapsed):
 assert n>0 and count>0 and elapsed>0
 return {'gemms_per_second':count/elapsed,'ms_per_gemm':elapsed*1000/count,'tflops':2*n**3*count/elapsed/1e12}

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',type=int,required=True);p.add_argument('--mode',choices=['correctness','performance'],required=True);p.add_argument('--out',required=True);p.add_argument('--model');p.add_argument('--fixture');p.add_argument('--input');p.add_argument('--backend',choices=['native','vmweave'],required=True);p.add_argument('--diagnostic',action='store_true');a=p.parse_args()
 n=a.batch;assert n in [4096,8192,16384,20480];size=n*n*4;assert 3*size+WORKSPACE<BUDGET
 if a.backend=='vmweave':rt=blas=C.CDLL('/tmp/perf/libflyt_guest.so')
 else:rt=C.CDLL('libcudart.so.12');blas=C.CDLL('libcublas.so.12')
 def fn(lib,name,args):
  f=getattr(lib,name);f.argtypes=args;f.restype=C.c_int
  def checked(*args):
   rc=f(*args)
   if rc:raise RuntimeError(f'{name} returned {rc}')
  return checked
 ptr=C.c_void_p;P=C.POINTER
 malloc=fn(rt,'cudaMalloc',[P(ptr),C.c_size_t]);free=fn(rt,'cudaFree',[ptr]);copy=fn(rt,'cudaMemcpy',[ptr,ptr,C.c_size_t,C.c_int]);sync=fn(rt,'cudaDeviceSynchronize',[])
 info=fn(rt,'cudaMemGetInfo',[P(C.c_size_t),P(C.c_size_t)])
 create=fn(blas,'cublasCreate_v2',[P(ptr)]);destroy=fn(blas,'cublasDestroy_v2',[ptr]);streamcreate=fn(rt,'cudaStreamCreate',[P(ptr)]);streamdestroy=fn(rt,'cudaStreamDestroy',[ptr])
 setstream=fn(blas,'cublasSetStream_v2',[ptr,ptr]);setmath=fn(blas,'cublasSetMathMode',[ptr,C.c_int]);getmath=fn(blas,'cublasGetMathMode',[ptr,P(C.c_int)]);setpointer=fn(blas,'cublasSetPointerMode_v2',[ptr,C.c_int]);getpointer=fn(blas,'cublasGetPointerMode_v2',[ptr,P(C.c_int)]);setworkspace=fn(blas,'cublasSetWorkspace_v2',[ptr,ptr,C.c_size_t])
 gemm=fn(blas,'cublasSgemm_v2',[ptr,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,P(C.c_float),ptr,C.c_int,ptr,C.c_int,P(C.c_float),ptr,C.c_int])
 def memory():
  f,t=C.c_size_t(),C.c_size_t();info(C.byref(f),C.byref(t));return {'free':f.value,'total':t.value,'used':t.value-f.value}
 def stats():
  result={}
  for name,count in [('vmweave_broker_cache_stats',6),('vmweave_broker_math_cache_stats',5)]:
   if hasattr(rt,name):
    f=getattr(rt,name);f.argtypes=[P(C.c_uint64)];f.restype=None;arr=(C.c_uint64*count)();f(arr);result[name]=list(arr)
  return result
 h,st,workspace=ptr(),ptr(),ptr();arrays=[];started=time.time();meta={'n':n,'shape':[n,n],'dtype':'float32','layout':'column-major','backend':a.backend,'mode':a.mode,'diagnostic':a.diagnostic,'numpy':np.__version__,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'workspace_bytes':WORKSPACE,'group_size':16,'tf32_policy':'CUBLAS_PEDANTIC_MATH','input_seeds':[20261022,20261023]}
 try:
  baseline=memory();create(C.byref(h));streamcreate(C.byref(st));setstream(h,st);setmath(h,2);setpointer(h,0)
  malloc(C.byref(workspace),WORKSPACE);setworkspace(h,workspace,WORKSPACE)
  mm,pm=C.c_int(),C.c_int();getmath(h,C.byref(mm));getpointer(h,C.byref(pm));assert mm.value==2 and pm.value==0
  version=C.c_int();fn(blas,'cublasGetVersion_v2',[ptr,P(C.c_int)])(h,C.byref(version)) if a.backend=='native' else None
  meta.update(math_mode=mm.value,pointer_mode=pm.value,cublas_version=version.value or None,memory_before=baseline)
  for _ in range(3):
   v=ptr();malloc(C.byref(v),size);arrays.append(v)
  hashes=[]
  for seed,v in zip(meta['input_seeds'],arrays):
   digest=hashlib.sha256()
   for lo in range(0,n*n,CHUNK):
    count=min(CHUNK,n*n-lo);x=values(np.arange(lo,lo+count,dtype=np.uint32),seed,n);assert x.dtype==np.float32 and x.size==count
    digest.update(x.tobytes());copy(ptr(v.value+lo*4),ptr(x.ctypes.data),x.nbytes,1)
   hashes.append(digest.hexdigest())
  meta['input_sha256']=hashes
  alpha,beta=C.c_float(1),C.c_float(0)
  def launch():gemm(h,0,0,n,n,n,C.byref(alpha),arrays[0],n,arrays[1],n,C.byref(beta),arrays[2],n)
  launch();sync();meta['memory_ready']=memory();assert meta['memory_ready']['used']<=BUDGET,meta['memory_ready']
  if a.mode=='correctness':
   checksum=hashlib.sha256();finite=True;sample_indices=[(i*104729)%(n*n) for i in range(16)];samples={}
   with open(a.out+'.pt','wb') as out:
    for lo in range(0,n*n,CHUNK):
     count=min(CHUNK,n*n-lo);x=np.empty(count,dtype=np.float32);copy(ptr(x.ctypes.data),ptr(arrays[2].value+lo*4),x.nbytes,2)
     finite=finite and bool(np.isfinite(x).all());data=x.tobytes();out.write(data);checksum.update(data)
     for idx in sample_indices:
      if lo<=idx<lo+count:samples[idx]=float(x[idx-lo])
   assert finite
   refs=[]
   for idx in sample_indices:
    row,col=idx%n,idx//n;k=np.arange(n,dtype=np.uint32)
    av=values(row+k*n,20261022,n).astype(np.float64);bv=values(k+col*n,20261023,n).astype(np.float64);ref=float(np.dot(av,bv));error=abs(samples[idx]-ref)
    assert error<=1e-5+1e-4*abs(ref),(idx,samples[idx],ref)
    refs.append({'index':idx,'actual':samples[idx],'fp64_reference':ref,'abs_error':error})
   meta.update(output_sha256=checksum.hexdigest(),output_bytes=size,finite=True,cpu_reference=refs)
  else:
   warm=0;t=time.monotonic()
   while warm<30 or time.monotonic()-t<5:
    for _ in range(16):launch();warm+=1
    sync()
   warm_seconds=time.monotonic()-t;before=stats()
   if a.backend=='vmweave':assert all(before[k][0]==1 for k in before)
   if a.diagnostic:
    profiler=C.CDLL(None);pid=int(Path('/tmp/perf/broker-profile.pid').read_text());Path('/tmp/perf/profile-started').unlink(missing_ok=True);Path('/tmp/perf/broker-api-timing.json').unlink(missing_ok=True);os.kill(pid,signal.SIGUSR1)
    deadline=time.monotonic()+10
    while not Path('/tmp/perf/profile-started').exists():
     assert time.monotonic()<deadline;time.sleep(.001)
    profiler.diag_profile_start()
   cpu0=resource.getrusage(resource.RUSAGE_SELF);wall=time.time();t=time.monotonic();completed=0;groups=[]
   print(json.dumps({'event':'measurement_start','utc':wall,'n':n}),flush=True)
   while (completed<64 if a.diagnostic else time.monotonic()-t<60):
    t0=time.monotonic()
    for _ in range(16):launch()
    sync();completed+=16;groups.append(time.monotonic()-t0)
   elapsed=time.monotonic()-t;end=time.time();cpu1=resource.getrusage(resource.RUSAGE_SELF)
   if a.diagnostic:
    profiler.diag_profile_stop();os.kill(pid,signal.SIGUSR2);deadline=time.monotonic()+10
    while not Path('/tmp/perf/broker-api-timing.json').exists():
     assert time.monotonic()<deadline;time.sleep(.001)
   meta.update(start_utc=wall,end_utc=end,completed_gemms=completed,elapsed_seconds=elapsed,warmup_gemms=warm,warmup_seconds=warm_seconds,group_seconds=groups,cache_before=before,cache_after=stats(),guest_cpu_seconds=(cpu1.ru_utime+cpu1.ru_stime)-(cpu0.ru_utime+cpu0.ru_stime),**metrics(n,completed,elapsed))
   meta['memory_after']=memory();assert meta['memory_after']['used']<=BUDGET
  meta['setup_and_run_seconds']=time.time()-started
  Path(a.out+'.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({k:v for k,v in meta.items() if k!='group_seconds'}),flush=True)
 finally:
  sync()
  for v in arrays:free(v)
  if h.value:destroy(h)
  if workspace.value:free(workspace)
  if st.value:streamdestroy(st)
if __name__=='__main__':main()
