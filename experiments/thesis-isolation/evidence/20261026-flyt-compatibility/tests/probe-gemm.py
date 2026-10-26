import json,subprocess,shlex
from pathlib import Path
b=Path('.local/flyt-compatibility-20261026'); c=json.loads((b/'a/ssh.json').read_text())
code='''import ctypes as C,json
l=C.CDLL('/tmp/flyt-test/cricket-client.so'); h=C.c_void_p(); statuses={'create':l.cublasCreate_v2(C.byref(h))}; a=C.c_void_p();b=C.c_void_p();c=C.c_void_p()
for n,p in [('a',a),('b',b),('c',c)]:statuses['malloc_'+n]=l.cudaMalloc(C.byref(p),C.c_size_t(16))
x=(C.c_float*4)(1,2,3,4);y=(C.c_float*4)(5,6,7,8);out=(C.c_float*4)();alpha=C.c_float(1);beta=C.c_float(0)
statuses['h2d_a']=l.cudaMemcpy(a,x,C.c_size_t(16),1);statuses['h2d_b']=l.cudaMemcpy(b,y,C.c_size_t(16),1)
l.cublasSgemm_v2.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.POINTER(C.c_float),C.c_void_p,C.c_int,C.c_void_p,C.c_int,C.POINTER(C.c_float),C.c_void_p,C.c_int]
statuses['gemm']=l.cublasSgemm_v2(h,0,0,2,2,2,C.byref(alpha),a,2,b,2,C.byref(beta),c,2)
statuses['sync']=l.cudaDeviceSynchronize();statuses['d2h']=l.cudaMemcpy(out,c,C.c_size_t(16),2)
print(json.dumps(dict(statuses=statuses,values=list(out),correct=list(out)==[23,34,31,46] and not any(statuses.values()))),flush=True)
for p in [a,b,c]:l.cudaFree(p)
l.cublasDestroy_v2(h)
'''
p=subprocess.run(c['ssh']+['sudo timeout -k 5 30 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs /opt/torch-venv/bin/python3 -u -c '+shlex.quote(code)],capture_output=True,text=True,timeout=40)
out=p.stdout+p.stderr; print(out); Path('experiments/thesis-isolation/results/20261026-flyt-compatibility/validation/minimal-gemm.log').write_text(out)
