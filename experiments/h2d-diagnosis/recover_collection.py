"""Restart the complete main comparison after an artifact-collection race."""
from common import *
import hashlib,shutil
assert not (OUT/'main-complete.json').exists()
assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
for n in ['probe-S','probe-T']:shutil.copy2(BASE/'diagnostic'/n,BASE/('initial-'+n))
shutil.copy2(OUT/'protocol-main.json',OUT/'protocol-main-initial.json')
command="gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/h2d-diagnosis/probe.c -L/out/artifacts -Wl,-rpath,'$ORIGIN' -lflyt_guest -o /out/diagnostic/probe-S\ngcc -O2 -DFLYT_TCP -I/usr/local/cuda/include /repo/experiments/h2d-diagnosis/probe.c -L/out/artifacts -Wl,-rpath,'$ORIGIN' -Wl,-rpath-link,/out/artifacts -Wl,--allow-shlib-undefined -l:cricket-client.so -o /out/diagnostic/probe-T"
call(['taskset','-c','48-51','podman','run','--rm','-v',str(ROOT)+':/repo:ro','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
call([os.sys.executable,ROOT/'experiments/h2d-diagnosis/smoke_collection.py'],timeout=900)
call([os.sys.executable,ROOT/'experiments/h2d-diagnosis/freeze_main.py'])
p=json.loads((OUT/'protocol-main.json').read_text());p['run_prefix']='hd-main-v2-r';p['recovery']={'reason':'Initial r3-S completed CUDA validation and CSV capture, but VM automatic release raced independent SHA256 collection. Preserve all initial runs separately; restart ALL 10 formal sessions with the same fixed collection method. No performance-based exclusion.','change':'Only post-measurement atexit barrier added to probe: collect CSV and independently hash output while CUDA session remains alive, then release process; timed operations unchanged.','initial_protocol':'protocol-main-initial.json','initial_attempts_not_pooled':True};save(OUT/'protocol-main.json',p)
save(OUT/'preflight/collection-recovery.json',{'utc':time.time(),**p['recovery']})
