"""Nine fresh VM/Worker runs; keep administrative audit outside published data."""
import json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'experiments/sm-core-limit/evidence/limit-validation-20261015'
AUDIT=ROOT/'.local/sm-core-limit-20261015/validation-audit'
os.environ['SM_TEST_OUT']=str(AUDIT)
os.environ['SM_TEST_GPU']='GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a'
import vmweave
c=vmweave.common
OUT.mkdir(parents=True,exist_ok=True)
order=[25,50,75,75,50,25,50,25,75]
c.save(OUT/'protocol.json',dict(order=order,seconds=150,warmup=30,reps=1048576,variant='idle-reset',gpu_uuid=os.environ['SM_TEST_GPU'],fresh_vm_and_worker=True))
for index,cap in enumerate(order,1):
    dest=OUT/f'run-{index:02d}-limit-{cap}'
    if (dest/'result.json').exists():
        raise RuntimeError('Refusing to overwrite completed run '+str(dest))
    before=set((AUDIT/'runs').glob('*')) if (AUDIT/'runs').exists() else set()
    print(f'START {index}/9 limit={cap}',flush=True)
    subprocess.run([sys.executable,str(Path(vmweave.__file__)), '--variant','idle-reset','--limit',str(cap),'--seconds','150','--warmup','30'],check=True,env=os.environ)
    fresh=set((AUDIT/'runs').glob('*'))-before
    assert len(fresh)==1,fresh
    source=fresh.pop();dest.mkdir()
    import shutil
    for name in ['result.json','gpu.csv','probe.stdout','probe.stderr','library-mount.json','worker-libraries.json','identity.json','cleanup.json','channel-bound.json','channel-released.json','worker-output.txt']:
        shutil.copy2(source/name,dest/name)
    c.save(dest/'run.json',dict(index=index,limit=cap,source_run=source.name,completed_utc=time.time()))
    c.admin(['chroot','/host','rm','-rf','/var/lib/vmweave/thesis-isolation-20261012/'+source.name])
    print(f'DONE {index}/9',flush=True)
for cap in [25,50,75]:
    c.k('delete','gpuprofiles.vmweave.io','sm-core-canary-'+str(cap)+'-'+os.environ['SM_TEST_GPU'][-8:],'-n',c.NS,'--ignore-not-found')
c.save(OUT/'completed.json',dict(runs=9,utc=time.time()))
