from common import *
import hashlib,shutil
assert (OUT/'main-complete.json').exists()
assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
for n in ['probe-S','probe-T']:shutil.copy2(BASE/'diagnostic'/n,BASE/('main-'+n))
call([os.sys.executable,ROOT/'experiments/h2d-diagnosis/build_final_diagnostics.py'],timeout=900)
call([os.sys.executable,ROOT/'experiments/h2d-diagnosis/build_off.py'],timeout=600)
command="gcc -O2 -DFLYT_GUEST -I/usr/local/cuda/include /repo/experiments/h2d-diagnosis/followup_probe.c -L/out/artifacts -Wl,-rpath,'$ORIGIN' -lflyt_guest -o /out/diagnostic/probe-S\ngcc -O2 -I/repo/runtime/shm/include -I/repo/runtime/shm/shm-queue/include -I/repo/runtime/shm/shm-contract/include /repo/experiments/h2d-diagnosis/map_probe.c /repo/runtime/shm/src/mapping.c /repo/runtime/shm/shm-queue/src/queue.c /repo/runtime/shm/shm-queue/src/perf.c -pthread -o /out/diagnostic/map-probe"
call(['taskset','-c','48-51','podman','run','--rm','-v',str(ROOT)+':/repo:ro','-v',str(BASE)+':/out','localhost/flyt-build:stage2-20260928','sh','-ec',command],timeout=600)
# Verify the final binaries and post-CUDA teardown before freezing formal trials.
call([os.sys.executable,ROOT/'experiments/h2d-diagnosis/smoke_final.py'],timeout=900)
sessions=[]
for r in range(1,6):
 order=[('cause','original',True),('cause','direct',True),('confirm','original',False),('confirm','direct',False)]
 shift=(r-1)%4;order=order[shift:]+order[:shift]
 for phase,v,metrics in order:
  sessions.append({'name':f'hd-{phase}-r{r}-{v}','variant':v,'metrics':metrics,'mode':'patterns' if metrics else 'regression','seconds':60,'warmup':10,'pattern_order':r%2,'map_probe':phase=='confirm' and r==1})
for name,cpus in [('control','16-19'),('local','8-11')]:
 sessions.append({'name':'hd-numa-'+name,'variant':'original','metrics':True,'mode':'copy','seconds':60,'warmup':10,'worker_cpus':cpus})
save(OUT/'protocol-followup.json',{'frozen_utc':time.time(),'purpose':'Causal one-copy removal, instrumentation on/off calibration, small-copy regression, H2D-only pattern diagnostic, supplementary CPU/NUMA placement pair.','sessions':sessions,'primary':'16MiB alternating copy:5 independent sessions/condition,60s,min10s+50operations warmup','supplementary':'H2D-only and4KiB/64KiB/1MiB:5 independent sessions/condition,10s,min3s+50operations warmup; do not present these as60s trials. BAR component:2 VM sessions,2s inclusive warmup per size/mode,first20operations discarded. CPU/NUMA:one matched pair, exploratory only.','order_control':'Metrics ON and OFF use identical copy/H2D-only order in each repeat; OFF-only small-copy checks follow both windows.', 'causal_change':'Guest payload goes directly to the SHM request arena while the private48-byte header and Worker-private snapshot/validation remain. Synchronous caller retains input until return. This is not GPU zero-copy.','runtime':'Guest and Worker final diagnostic v3 with teardown correction; exact same Worker executable across controls/candidate, only metrics environment differs. Production defaults unchanged.','hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'diagnostic/probe-S',BASE/'diagnostic/libflyt_guest.so',BASE/'diagnostic/bin/flyt-shm-worker',BASE/'diagnostic/map-probe']},'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'experiments/h2d-diagnosis').glob('*') if p.is_file()}})
