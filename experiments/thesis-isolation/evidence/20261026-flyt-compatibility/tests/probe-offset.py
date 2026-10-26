import json,subprocess,shlex
from pathlib import Path
b=Path('.local/flyt-compatibility-20261026'); c=json.loads((b/'a/ssh.json').read_text())
code='''import ctypes as C,json
l=C.CDLL('/tmp/flyt-test/cricket-client.so'); p=C.c_void_p(); x=(C.c_float*4)(1,2,3,4); y=(C.c_float*1)()
a=l.cudaMalloc(C.byref(p),C.c_size_t(16)); h=l.cudaMemcpy(p,x,C.c_size_t(16),1); d=l.cudaMemcpy(y,C.c_void_p(p.value+4),C.c_size_t(4),2); f=l.cudaFree(p)
print(json.dumps(dict(malloc=a,base_h2d=h,offset_d2h=d,value=y[0],free=f,client_address=hex(p.value))))
'''
p=subprocess.run(c['ssh']+['sudo timeout -k 5 30 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs /opt/torch-venv/bin/python3 -u -c '+shlex.quote(code)],capture_output=True,text=True,timeout=40)
out=p.stdout+p.stderr; print(out); Path('experiments/thesis-isolation/results/20261026-flyt-compatibility/validation/offset-before.log').write_text(out)
