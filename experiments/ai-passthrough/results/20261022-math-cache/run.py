"""Site-specific isolated canary. Does not patch shared allocator or live VM."""
import json,os,sys,shutil,subprocess,time,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;BASE=ROOT/'.local/math-cache-20261022';OUT=BASE/'results'
sys.path.insert(0,str(ROOT/'experiments/ai-passthrough/runner'))
import campaign as old
assert (BASE/'build/libflyt_guest.so').read_bytes()!=(BASE/'build/libvmweave_guest.so').read_bytes(), 'baseline/candidate must be distinct'
OUT.mkdir(exist_ok=False);old.BASE=BASE;old.OUT=OUT;c,s=old.c,old.s;c.OUT=s.OUT=OUT/'audit';c.HELPER=s.HELPER='vmweave-math-cache-admin-1022'
s.GPU='GPU-772181af-05a4-0c24-de59-8487bd37c142';s.IMAGES['worker']=json.loads((ROOT/'deploy/releases/v0.5.1.json').read_text())['images']['worker']
original=c.call

def call(args,**kw):
 args=list(map(str,args))
 if args[0]=='scp' and str(ROOT/'runtime/shm/control/guest_broker.py') in args:
  args[-1:-1]=[str(ROOT/'runtime/shm/control/vmweave_env.py'),str(D/'broker_profile.py')]
 if args[0]=='ssh' and 'nohup' in args[-1]:args[-1]=args[-1].replace('/tmp/perf/guest_broker.py','/tmp/perf/broker_profile.py')
 return original(args,**kw)
c.call=call
original_k=s.k

def k(*args,**kw):
 if 'input' in kw and 'No QEMU/Worker process matched' in kw['input']:kw['input']=kw['input'].replace("'flyt-shm-worker'","'vmweave-shm-worker','vmweave-shm-session-worker','flyt-shm-worker'")
 return original_k(*args,**kw)
s.k=k
original_wait=s.wait

def wait(fn,seconds=300):
 if 'BackingReady' in fn.__code__.co_consts:return original_wait(lambda:v.get(s.CHAN,v.name).get('status',{}).get('phase') in ('BackingReady','Bound','Ready'),seconds)
 return original_wait(fn,seconds)
s.wait=wait
v=old.VM('ai-math-cache-1022');v.profile_name='ai-math-cache-1022-profile';v.install=lambda:None
try:
 c.ensure_admin();v.prepare()
 for source,name in [(BASE/'build/libflyt_guest.so','baseline.so'),(BASE/'build/libvmweave_guest.so','candidate.so'),(BASE/'client-profile.so','client-profile.so'),(D/'bench.py','headroom-bench.py')]:c.call(v.scp+[str(source),'ubuntu@'+v.ip+':/tmp/perf/'+name])
 base=v.benchcmd
 jobs=[('correctness-baseline',False,False,'correctness'),('correctness-candidate',True,False,'correctness'),('profile-baseline',False,True,'performance'),('profile-candidate',True,True,'performance')]
 for b in range(1,4):jobs += [(f'b{b}-baseline',False,False,'performance'),(f'b{b}-candidate',True,False,'performance'),(f'b{b}-restored',False,False,'performance')]
 for label,candidate,profile,mode in jobs:
  library='candidate.so' if candidate else 'baseline.so';c.call(v.ssh+['ln -sfn '+library+' /tmp/perf/libcuda.so.1'])
  def command(args):
   cmd=base(args);preload=('/tmp/perf/client-profile.so:' if profile else '')+'/tmp/perf/'+library
   cmd[-1]=cmd[-1].replace('LD_PRELOAD=/tmp/perf/libflyt_guest.so',f'FLYT_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE={int(candidate)} VMWEAVE_DIAG_PROFILE={int(profile)} LD_PRELOAD={preload}').replace('/tmp/perf/bench.py','/tmp/perf/headroom-bench.py').replace('FLYT_','VMWEAVE_')
   return cmd
  v.benchcmd=command;dest=OUT/label;old.measure(v,('small',1024,'resident'),mode,dest)
  if profile:
   for name in ['client-api-timing.json','broker-api-timing.json']:c.call(v.scp+['ubuntu@'+v.ip+':/tmp/perf/'+name,str(dest/name)])
  if mode=='performance':
   r=json.loads((dest/'result.json').read_text());assert r['steps']==200 and r['warmup_steps']==30 and r['cache_after'][0]==1
   print(label,r['samples_per_second'],flush=True)
 c.call(v.scp+['ubuntu@'+v.ip+':/tmp/perf/broker.log',str(OUT/'broker.log')])
 # Explicit real-GPU mode, multi-handle, error and fresh-session probes.
 c.call(v.scp+[str(D/'gpu_semantics.py'),'ubuntu@'+v.ip+':/tmp/perf/gpu_semantics.py'])
 c.call(v.ssh+['ln -sfn candidate.so /tmp/perf/libcuda.so.1'])
 probe='VMWEAVE_STATE_CACHE=1 VMWEAVE_BLAS_MATH_CACHE=1 VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock LD_PRELOAD=/tmp/perf/candidate.so LD_LIBRARY_PATH=/tmp/perf:/opt/flyt-cuda-libs /opt/torch-venv/bin/python /tmp/perf/gpu_semantics.py'
 for attempt in range(2):
  result=c.call(v.ssh+[probe]);(OUT/f'gpu-semantics-{attempt}.json').write_text(result)
 (OUT/'guest-hashes.txt').write_text(c.call(v.ssh+['sha256sum /tmp/perf/baseline.so /tmp/perf/candidate.so']))
 (OUT/'complete.json').write_text(json.dumps({'status':'PASS','worker_image':s.IMAGES['worker']}))
finally:
 if not v.uid:
  current=c.get(s.CHAN,v.name,ns=v.ns)
  if current:v.uid=current['metadata']['uid']
 v.cleanup()
 c.k('delete','gpurequest',v.name,'-n',v.ns,'--ignore-not-found')
 c.k('delete','gpuprofile',v.profile_name,'-n',v.ns,'--ignore-not-found')
 c.k('delete','pod',c.HELPER,'-n',v.ns,'--ignore-not-found','--wait=true','--timeout=60s')
