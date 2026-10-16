"""Three fresh two-VM trials, patched HAMi, shared GPU and coordinated starts."""
import json,os,sys,time,subprocess,threading,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'.local/sm-pair-20261016';OUT=ROOT/'experiments/sm-core-limit/evidence/pairs-20261016'
os.environ['SM_TEST_OUT']=str(BASE/'audit');os.environ['SM_TEST_GPU']='GPU-c654d43e-43f8-c28e-77c2-1f17a0cbf46a'
import vmweave
c=vmweave.common;smod=vmweave.session
c.OUT=smod.OUT=BASE/'audit';c.HELPER=smod.HELPER='sm-pair-admin-1016'
# Wait for the executable, not just the Pod's Running phase, before affinity pinning.
def ready_k(*args,**kw):
 end=time.monotonic()+120
 while True:
  try:return c.k(*args,**kw)
  except RuntimeError as e:
   if 'No QEMU/Worker process matched exact Pod UID' not in str(e) or time.monotonic()>end:raise
   time.sleep(2)
smod.k=ready_k
class PairVM(vmweave.Canary):
 def __init__(self,name,cap,slot):
  super().__init__(name,'idle-reset',cap)
  self.slot=slot;self.ns='vmweave-test-'+slot;self.profile_name=f'sm-pair-{cap}-20261016'
 def prepare(self):
  super().prepare()
  c.call(self.scp+[str(BASE/'sm-pair-probe-guest'),'ubuntu@'+self.ip+':/tmp/perf/'])
  c.save(self.out/'worker.json',self.get('pod',self.worker));c.save(self.out/'vmi.json',self.get('vmi',self.name))
  script='''from pathlib import Path
import json,sys
uid=sys.argv[1];rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  if p.joinpath('exe').readlink().name!='flyt-shm-worker.original':continue
  env=dict(x.split('=',1) for x in (p/'environ').read_text().split('\\0') if '=' in x)
  rows.append(dict(pid=int(p.name),maps=(p/'maps').read_text(),env={k:v for k,v in env.items() if k.startswith(('CUDA_DEVICE','GPU_CORE','FLYT_RESOURCE'))}))
 except (OSError,ValueError):pass
assert len(rows)==1,rows
print(json.dumps(rows[0]))
'''
  uid=self.get('pod',self.worker)['metadata']['uid']
  info=json.loads(c.k('exec','-i','-n',c.NS,c.HELPER,'--','chroot','/host','python3','-',uid,input=script))
  assert int(info['env']['CUDA_DEVICE_SM_LIMIT'])==self.cap,info
  assert info['env']['GPU_CORE_UTILIZATION_POLICY']=='FORCE'
  c.save(self.out/'host-process.json',info)
  self.host_pid=info['pid']
 def cleanup(self):
  self.close()
  if self.uid:
   for kind in [smod.CHAN,'vm','pvc']:c.k('delete',kind,self.name,'-n',self.ns,'--ignore-not-found','--wait=true','--timeout=60s')
   c.k('delete','pv',self.name,'--ignore-not-found','--wait=true','--timeout=60s')
   c.admin(['chroot','/host','rm','-rf','/var/lib/vmweave/thesis-isolation-20261012/'+self.name])
def publish(vm,dest):
 dest.mkdir(parents=True,exist_ok=True)
 for name in ['library-mount.json','worker-libraries.json','host-process.json','identity.json','worker.json','vmi.json','channel-bound.json','channel-released.json','cleanup.json','clock-map.json','probe.stdout','probe.stderr','events.jsonl','worker-output.txt']:
  p=vm.out/name
  if p.exists():shutil.copyfile(p,dest/name)
 for p in vm.out.glob('*-affinity.json'):shutil.copyfile(p,dest/p.name)

def trial(index,caps):
 dest=OUT/f'pair-{index}';dest.mkdir(parents=True,exist_ok=False)
 vms=[PairVM(f'sm-pair-r{index}-{slot}-1016',cap,slot) for slot,cap in zip('ab',caps)]
 processes=[];threads=[];handles=[];events=[[],[]]
 try:
  for v in vms:
   print('PREPARING',v.name,flush=True);v.prepare();print('PREPARED',v.name,flush=True)
  start=time.time()+25
  config={'index':index,'caps':caps,'gpu_uuid':smod.GPU,'start_utc':start,'seconds':180,'warmup':30,'reps':1048576,'workers':[v.worker for v in vms],'host_pids':[v.host_pid for v in vms],'names':[v.name for v in vms],'clock_offsets':[v.offset for v in vms]}
  c.save(dest/'protocol.json',config);c.save(BASE/'state.json',config)
  def read(i,p,v):
   with (v.out/'probe.stdout').open('w') as raw,(v.out/'events.jsonl').open('w') as out:
    for line in p.stdout:
     raw.write(line);raw.flush()
     try:r=json.loads(line)
     except json.JSONDecodeError:continue
     r['received_utc']=time.time();events[i].append(r);out.write(json.dumps(r)+'\n');out.flush()
  for i,v in enumerate(vms):
   err=(v.out/'probe.stderr').open('w');handles.append(err)
   p=subprocess.Popen(v.command('sm-pair-probe-guest',[180,30,1048576,start+v.offset]),stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1);processes.append(p)
   t=threading.Thread(target=read,args=(i,p,v));t.start();threads.append(t)
  print('MEASURING',index,json.dumps(config),flush=True)
  deadline=start+240
  while any(p.poll() is None for p in processes):
   if time.time()>deadline:raise TimeoutError('Concurrent probes timed out')
   time.sleep(1)
  for t in threads:t.join(timeout=10)
  assert all(p.returncode==0 for p in processes),[p.returncode for p in processes]
  results=[next(r for r in ev if r['event']=='result') for ev in events]
  assert all(any(r['event']=='ready' and r['received_utc']<start for r in ev) for ev in events),'Missed start barrier'
  c.save(dest/'result.json',{'protocol':config,'results':results,'returncodes':[p.returncode for p in processes],'completed_utc':time.time()})
  print('RESULT',index,json.dumps(results),flush=True)
 finally:
  for p in processes:
   if p.poll() is None:p.terminate();p.wait(timeout=15)
  for t in threads:t.join(timeout=10)
  for f in handles:f.close()
  errors=[]
  for v in vms:
   try:v.cleanup()
   except Exception as e:errors.append({'vm':v.name,'error':repr(e)})
   finally:publish(v,dest/v.slot)
  c.save(dest/'cleanup.json',{'errors':errors,'utc':time.time()})
  if errors:raise RuntimeError(str(errors))
 print('DONE',index,flush=True)

if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True);c.ensure_admin()
 digest=c.admin(['chroot','/host','podman','image','inspect','localhost/vmweave-worker:sm-core-canary-20261015','--format','{{.Digest}}']).strip()
 smod.IMAGES['worker']='localhost/vmweave-worker@'+digest
 if smod.GPU in c.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader']):raise RuntimeError('GPU occupied')
 expected='f30f08c8f4bbdada1856231f2ec269d50fc81e08881a4146c9c1bbb3173aebd8'
 assert hashlib.sha256((vmweave.ART/'libvgpu-idle-reset.so').read_bytes()).hexdigest()==expected
 c.save(OUT/'protocol.json',{'order':[[25,75],[75,25],[25,75]],'gpu_uuid':smod.GPU,'library_sha256':expected,'memory_mib_per_vm':2048,'new_vm_each_trial':True,'seconds':180,'warmup':30,'measurement_host_window':'start+35 <= timestamp < start+178','scope':'Two isolated Workers use the exact release library in Pod-local read-only mounts; cluster-wide HAMi unchanged.'})
 try:
  for i,caps in enumerate([[25,75],[75,25],[25,75]],1):trial(i,caps)
  c.save(OUT/'completed.json',{'trials':3,'vms':6,'utc':time.time()})
 finally:
  for ns in ['vmweave-test-a','vmweave-test-b']:
   for cap in [25,75]:c.k('delete','gpuprofiles.vmweave.io',f'sm-pair-{cap}-20261016','-n',ns,'--ignore-not-found',check=False)
