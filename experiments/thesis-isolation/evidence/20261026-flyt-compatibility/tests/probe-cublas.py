import json,subprocess,shlex
from pathlib import Path
b=Path('.local/flyt-compatibility-20261026'); c=json.loads((b/'a/ssh.json').read_text())
code='''import ctypes as C,json
l=C.CDLL('/tmp/flyt-test/cricket-client.so'); h=C.c_void_p(); s=l.cublasCreate_v2(C.byref(h)); print(json.dumps(dict(cublas_create=s,handle=h.value)),flush=True)
if s==0: print('destroy',l.cublasDestroy_v2(h),flush=True)
'''
p=subprocess.run(c['ssh']+['sudo timeout -k 5 30 env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs /opt/torch-venv/bin/python3 -u -c '+shlex.quote(code)],capture_output=True,text=True,timeout=40)
out=p.stdout+p.stderr; print(out); Path('experiments/thesis-isolation/results/20261026-flyt-compatibility/validation/minimal-cublas.log').write_text(out)
