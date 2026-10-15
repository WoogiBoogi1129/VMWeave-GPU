"""Isolated VMWeave canary using the established allocation lifecycle runner.

Only the new canary Pod's library mount changes. The node's installed HAMi
library and pre-existing Worker Pods are never modified.
"""
import argparse, hashlib, json, os, subprocess, sys, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/thesis-isolation/runner'))
import common
common.OUT=Path(os.environ.get('SM_TEST_OUT',str(ROOT/'experiments/sm-core-limit/evidence/vmweave')))
common.HELPER='sm-core-admin-20261015'
import session
session.GPU=os.environ.get('SM_TEST_GPU','GPU-772181af-05a4-0c24-de59-8487bd37c142')
ART=ROOT/'.local/sm-core-limit-20261015/artifacts'

class Canary(session.Session):
 def __init__(self,name,variant,cap):
  super().__init__(name,cap=cap)
  self.variant=variant;self.profile_name='sm-core-canary-'+str(cap)+'-'+session.GPU[-8:]
  self.stop_gate=threading.Event();self.gate_error=None
 def install(self):
  try:
   deadline=time.monotonic()+240
   while not self.stop_gate.is_set() and time.monotonic()<deadline:
    pods=json.loads(common.k('get','pods','-n',self.ns,'-l','vmweave.io/channel='+self.name,'-o','json'))['items']
    pods=[p for p in pods if p['metadata']['name'].startswith(self.name+'-') and p['metadata']['name'].endswith('-worker') and p.get('status',{}).get('phase')=='Running']
    if pods:break
    time.sleep(1)
   else:raise TimeoutError('Canary Worker did not reach its gate')
   pod=pods[0];uid=pod['metadata']['uid'];name=pod['metadata']['name']
   assert pod['spec']['containers'][0]['image']==session.IMAGES['worker']
   src=ART/('libvgpu-'+self.variant+'.so')
   dst='/var/lib/vmweave/thesis-isolation-20261012/'+self.name+'/sm-lib.so'
   common.admin(['chroot','/host','cp',str(src),dst])
   script='''import pathlib,sys
uid=sys.argv[1];found=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text();cmd=(p/'cmdline').read_bytes()
  if (uid in cg or uid.replace('-','_') in cg) and b'/opt/flyt/control/supervisor.py' in cmd:found.append(int(p.name))
 except OSError:pass
assert len(found)==1,found
print(found[0])
'''
   pid=common.k('exec','-i','-n',common.NS,common.HELPER,'--','chroot','/host','python3','-',uid,input=script).strip()
   prefix=['chroot','/host','nsenter','--target',pid,'--mount','--pid','--root','--wd','--']
   common.admin(prefix+['mount','--bind','/flyt-channel/sm-lib.so','/usr/local/vgpu/libvgpu.so'])
   common.admin(prefix+['mount','-o','remount,bind,ro','/usr/local/vgpu/libvgpu.so'])
   actual=common.k('exec','-n',self.ns,name,'--','sha256sum','/usr/local/vgpu/libvgpu.so').split()[0]
   expected=hashlib.sha256(src.read_bytes()).hexdigest();assert actual==expected,(actual,expected)
   common.save(self.out/'library-mount.json',{'pod_uid':uid,'supervisor_host_pid':pid,'variant':self.variant,'sha256':actual,'mount_scope':'canary Pod mount namespace only'})
   common.k('exec','-n',self.ns,name,'--','touch','/tmp/sm-core-ready')
  except Exception as e:self.gate_error=repr(e)
 def prepare(self):
  self.thread=threading.Thread(target=self.install,daemon=True);self.thread.start()
  try:super().prepare()
  finally:
   self.stop_gate.set();self.thread.join(timeout=10)
  if self.gate_error:raise RuntimeError(self.gate_error)
  script='''from pathlib import Path
import json
rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  if p.joinpath('exe').readlink().name!='flyt-shm-worker.original':continue
  maps=p.joinpath('maps').read_text()
  rows.append({'pid':int(p.name),'libraries':sorted(set(l.split()[-1] for l in maps.splitlines() if 'libvgpu' in l or 'libcuda' in l))})
 except OSError:pass
assert len(rows)==1,rows
assert len([l for l in rows[0]['libraries'] if 'libvgpu' in l])==1,rows
print(json.dumps(rows))
'''
  identity=common.k('exec','-i','-n',self.ns,self.worker,'--','python3','-',input=script)
  (self.out/'worker-libraries.json').write_text(identity)
  common.call(self.scp+[str(ART/'sm-probe-guest'),'ubuntu@'+self.ip+':/tmp/perf/sm-probe-guest'])
 def measure(self,seconds,warmup,reps):
  cmd=self.command('sm-probe-guest',[seconds,warmup,reps])
  with (self.out/'probe.stdout').open('w') as out,(self.out/'probe.stderr').open('w') as err,(self.out/'gpu.csv').open('w') as samples:
   p=subprocess.Popen(cmd,stdout=out,stderr=err);start=time.monotonic()
   try:
    while p.poll() is None:
     if time.monotonic()-start>seconds+90:raise TimeoutError('Guest probe timed out')
     row=subprocess.check_output(['nvidia-smi','-i',session.GPU,'--query-gpu=utilization.gpu,memory.used,clocks.sm,power.draw','--format=csv,noheader,nounits'],text=True)
     samples.write(f'{time.monotonic()-start:.3f},'+row);samples.flush();time.sleep(1)
    if p.returncode:raise RuntimeError('Guest probe returned '+str(p.returncode))
   finally:
    if p.poll() is None:p.terminate();p.wait(timeout=15)
  rows=[json.loads(x) for x in (self.out/'probe.stdout').read_text().splitlines() if x.startswith('{')]
  result=next(x for x in rows if x['event']=='result')
  util=[float(x.split(',')[1]) for x in (self.out/'gpu.csv').read_text().splitlines() if float(x.split(',')[0])>=warmup+2]
  result.update(variant=self.variant,limit=self.cap,device_util_mean=sum(util)/len(util),samples=len(util))
  common.save(self.out/'result.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['original','patched','idle-reset'],required=True);ap.add_argument('--limit',type=int,default=50)
 ap.add_argument('--seconds',type=int,default=270);ap.add_argument('--warmup',type=int,default=30);ap.add_argument('--reps',type=int,default=1048576)
 a=ap.parse_args()
 digest=common.admin(['chroot','/host','podman','image','inspect','localhost/vmweave-worker:sm-core-canary-20261015','--format','{{.Digest}}']).strip()
 session.IMAGES['worker']='localhost/vmweave-worker@'+digest
 apps=common.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'])
 if session.GPU in apps:raise RuntimeError('Test GPU is occupied')
 s=Canary('sm-core-'+a.variant+'-'+str(a.limit)+'-'+time.strftime('%H%M%S',time.gmtime()),a.variant,a.limit)
 try:s.prepare();s.measure(a.seconds,a.warmup,a.reps)
 finally:
  s.close()
  if s.uid:
   # close() waits for controller detach and reclamation before object removal.
   for kind in ['sharedmemorychannels.vmweave.io','vm','pvc']:
    common.k('delete',kind,s.name,'-n',s.ns,'--ignore-not-found','--wait=true','--timeout=60s')
   common.k('delete','pv',s.name,'--ignore-not-found','--wait=true','--timeout=60s')
