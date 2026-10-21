"""Environment-specific pre-release name migration canary; one fixed workload.

Requires the retained 20261021 state-cache baseline and CUDA/VM fixtures.
No registry publication and no cluster-wide driver configuration changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import campaign as old

p=argparse.ArgumentParser()
p.add_argument('--worker-image',required=True)
p.add_argument('--artifacts',type=Path,required=True)
p.add_argument('--name',default='ai-naming-1022')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
ROOT=old.ROOT;BASE=ROOT/'.local/naming-release-20261022';OUT=a.output.resolve()
OUT.mkdir(parents=True,exist_ok=False)
old.BASE=BASE;old.OUT=OUT
c,s=old.c,old.s;c.OUT=s.OUT=OUT/'audit';c.HELPER=s.HELPER='vmweave-naming-admin-1022'
s.GPU='GPU-772181af-05a4-0c24-de59-8487bd37c142';s.IMAGES['worker']=a.worker_image
for name in ['small','medium','large']:
 shutil.copy2(ROOT/f'.local/ai-passthrough-20261021/{name}.pt',BASE/f'{name}.pt')
original_call=c.call

def call(args,**kwargs):
    args=list(map(str,args))
    if args[0]=='scp' and str(ROOT/'runtime/shm/control/guest_broker.py') in args:
        args.insert(-1,str(ROOT/'runtime/shm/control/vmweave_env.py'))
    return original_call(args,**kwargs)
c.call=call
original_k=s.k

def k(*args,**kwargs):
    if 'input' in kwargs and 'No QEMU/Worker process matched' in kwargs['input']:
        kwargs['input']=kwargs['input'].replace("'flyt-shm-worker'","'vmweave-shm-worker','vmweave-shm-session-worker','flyt-shm-worker'")
    return original_k(*args,**kwargs)
s.k=k
original_wait=s.wait

def wait(fn,seconds=300):
    if 'BackingReady' in fn.__code__.co_consts:
        return original_wait(lambda:v.get(s.CHAN,v.name).get('status',{}).get('phase') in ('BackingReady','Bound','Ready'),seconds)
    return original_wait(fn,seconds)
s.wait=wait

code=Path(__file__).with_name('bench.py').read_text()
code=code.replace('while time.monotonic()-t<a.warmup:\n  for _ in range(20):step();warmsteps+=1\n  torch.cuda.synchronize()', 'for _ in range(30):step();warmsteps+=1\n torch.cuda.synchronize()')
code=code.replace('while time.monotonic()-start<a.seconds:', 'while n<200:')
code=code.replace('start=time.monotonic();wall=time.time();c0=cpu();n=0', '''import ctypes
 lib=ctypes.CDLL(None)
 stats=getattr(lib,'vmweave_broker_cache_stats',None) or lib.flyt_broker_cache_stats
 def snapshot():
  values=(ctypes.c_uint64*6)();stats(values);return list(values)
 before=snapshot()
 start=time.monotonic();wall=time.time();c0=cpu();n=0''')
code=code.replace('torch.cuda.synchronize();elapsed=time.monotonic()-start;c1=cpu()', 'torch.cuda.synchronize();elapsed=time.monotonic()-start;c1=cpu()\n meta["cache_before"]=before;meta["cache_after"]=snapshot()')
bench=OUT/'bench.py';bench.write_text(code);compile(code,str(bench),'exec')
v=old.VM(a.name);v.profile_name=a.name+'-profile'
# Use the packaged Worker and the currently installed HAMi library unchanged.
v.install=lambda:None
try:
    c.ensure_admin()
    v.prepare()
    baseline=ROOT/'.local/vmweave-state-cache-20261021/build/libflyt_guest.so'
    for source,name in [(baseline,'baseline.so'),(a.artifacts/'libvmweave_guest.so','renamed.so'),(bench,'naming-bench.py')]:
        c.call(v.scp+[str(source),'ubuntu@'+v.ip+':/tmp/perf/'+name])
    base=v.benchcmd
    for label,canonical in [('baseline',False),('renamed',True),('restored',False)]:
        library='renamed.so' if canonical else 'baseline.so'
        c.call(v.ssh+['ln -sfn '+library+' /tmp/perf/libcuda.so.1'])
        def command(args):
            cmd=base(args)
            cmd[-1]=cmd[-1].replace('LD_PRELOAD=/tmp/perf/libflyt_guest.so',f'FLYT_STATE_CACHE=1 LD_PRELOAD=/tmp/perf/{library}').replace('/tmp/perf/bench.py','/tmp/perf/naming-bench.py')
            if canonical:cmd[-1]=cmd[-1].replace('FLYT_','VMWEAVE_')
            return cmd
        v.benchcmd=command
        if label!='restored':old.measure(v,('small',1024,'resident'),'correctness',OUT/('correctness-'+label))
        old.measure(v,('small',1024,'resident'),'performance',OUT/label)
        result=json.loads((OUT/label/'result.json').read_text())
        assert result['steps']==200 and result['warmup_steps']==30 and result['cache_after'][0]==1
        print('PASS',label,result['samples_per_second'],flush=True)
    comparison='''import json,sys,torch
from pathlib import Path
r=Path(sys.argv[1]);x=torch.load(r/'correctness-baseline/tensors.pt',map_location='cpu',weights_only=True);y=torch.load(r/'correctness-renamed/tensors.pt',map_location='cpu',weights_only=True)
for step in ['1','10','100']:
 assert torch.equal(x[step]['loss'],y[step]['loss'])
 for group in ['weights','gradients']:
  for name in x[step][group]:assert torch.equal(x[step][group][name],y[step][group][name])
(r/'correctness.json').write_text(json.dumps({'status':'PASS','max_abs_error':0,'steps':[1,10,100]}))
'''
    (OUT/'compare.py').write_text(comparison)
    c.call([str(ROOT/'.local/evidence-venv/bin/python'),str(OUT/'compare.py'),str(OUT)])
    c.save(OUT/'status.json',{'status':'PASS','worker_image':a.worker_image,'gpu':s.GPU,'baseline_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'renamed_sha256':hashlib.sha256((a.artifacts/'libvmweave_guest.so').read_bytes()).hexdigest()})
finally:
    if not v.uid:
        current=c.get(s.CHAN,v.name,ns=v.ns)
        if current:v.uid=current['metadata']['uid']
    v.cleanup()
    c.k('delete','gpurequest',v.name,'-n',v.ns,'--ignore-not-found')
    c.k('delete','gpuprofile',v.profile_name,'-n',v.ns,'--ignore-not-found')
