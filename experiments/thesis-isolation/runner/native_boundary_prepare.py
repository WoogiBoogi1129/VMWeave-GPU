"""Prepare an explicitly separate native CUDA/HAMi baseline; own access only."""
from campaign import Probe
from common import *
import hashlib,sys

name='iso-native-prep-'+time.strftime('%Y%m%d%H%M%S',time.gmtime());out=OUT/name;out.mkdir()
image=json.loads((BASE/'images.json').read_text())['worker']
sessions=[];probes=[];events=[];failure=None
save(out/'status.json',{'state':'PREPARING','utc':time.time(),'scope':'native own buffers and metadata queries only'})
save(out/'build.json',{'image':image,'probe_sha256':hashlib.sha256((BASE/'artifacts/native-boundary').read_bytes()).hexdigest(),
 'source_sha256':hashlib.sha256((ROOT/'experiments/thesis-isolation/probes/native_boundary.c').read_bytes()).hexdigest(),
 'guest_shim':False,'vmweave_worker':False,'memory_mib':2048,'gpu_core_setting':50,'physical_gpu_partition_claimed':False})
print('OUTPUT',out,flush=True)

class Native:
 def __init__(self,slot):
  self.slot=slot;self.name=name+'-'+slot;self.ns='vmweave-test-'+slot;self.uid=None;self.out=OUT/'runs'/self.name;self.out.mkdir()
 def prepare(self):
  obj={'apiVersion':'v1','kind':'Pod','metadata':{'name':self.name,'namespace':self.ns,'labels':{'vmweave.io/campaign':'performance-20260930'},'annotations':{'nvidia.com/use-gpuuuid':GPU}},
   'spec':{'restartPolicy':'Never','terminationGracePeriodSeconds':3,'automountServiceAccountToken':False,'runtimeClassName':'nvidia','schedulerName':'hami-scheduler','nodeSelector':{'kubernetes.io/hostname':'gpu-4'},
    'containers':[{'name':'native','image':image,'command':['sleep','900'],'resources':{'limits':{'nvidia.com/gpu':1,'nvidia.com/gpumem':2048,'nvidia.com/gpucores':50}},'volumeMounts':[{'name':'probe','mountPath':'/probe/native-boundary','readOnly':True}]}],
    'volumes':[{'name':'probe','hostPath':{'path':str(BASE/'artifacts/native-boundary'),'type':'File'}}]}}
  self.uid=create(obj)['metadata']['uid']
  wait(lambda:get('pod',self.name,ns=self.ns).get('status',{}).get('phase')=='Running',180)
  save(self.out/'pod.json',get('pod',self.name,ns=self.ns))
 def command(self,program,args):
  assert program=='native-boundary'
  return ['kubectl','exec','-i','-n',self.ns,self.name,'--','/probe/native-boundary',*map(str,args),GPU]
 def close(self):
  if not self.uid:return
  pod=get('pod',self.name,ns=self.ns)
  assert pod and pod['metadata']['uid']==self.uid
  k('delete','pod',self.name,'-n',self.ns,'--wait=true','--timeout=90s')
  assert get('pod',self.name,ns=self.ns) is None
  save(self.out/'cleanup.json',{'released':True,'uid':self.uid,'utc':time.time()})

def identify(s):
 script=r'''
import os,json,sys
from pathlib import Path
uid=sys.argv[1];rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text()
  if uid not in cg and uid.replace('-','_') not in cg:continue
  exe=os.readlink(p/'exe')
  if not exe.endswith('/native-boundary'):continue
  env=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split(chr(0)) if '=' in x)
  maps=(p/'maps').read_text()
  rows.append({'host_pid':int(p.name),'exe':exe,'nspid':[x for x in (p/'status').read_text().splitlines() if x.startswith('NSpid:')],
   'environment':{k:v for k,v in env.items() if k in ['LD_PRELOAD','CUDA_VISIBLE_DEVICES','CUDA_MPS_PIPE_DIRECTORY']},
   'libraries':sorted(set(x.split()[-1] for x in maps.splitlines() if any(y in x for y in ['libcuda','libvgpu','libflyt'])))})
 except (OSError,UnicodeDecodeError):continue
assert len(rows)==1,rows
print(json.dumps(rows[0]))
'''
 return json.loads(k('exec','-i','-n',NS,HELPER,'--','chroot','/host','python3','-',s.uid,input=script))
def command(p,op,event):
 rows=p.command(op);events.append({'process':p.s.name,'command':op,'rows':rows});save(out/'events.json',events)
 return next(x for x in rows if x['event']==event)
def check(p):
 r=command(p,'check','check');assert r['code']==0 and r['mismatches']==0,r

try:
 ensure_admin()
 assert GPU not in call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
 for slot in ['a','b']:
  s=Native(slot);sessions.append(s);s.prepare()
 for i,s in enumerate(sessions):
  p=Probe(s,202610141+i*100,program='native-boundary');probes.append(p);print('READY',s.slot,flush=True)
 identities=[identify(s) for s in sessions]
 assert identities[0]['host_pid']!=identities[1]['host_pid']
 for r in identities:
  assert any('libvgpu.so' in x for x in r['libraries'])
  assert not any('libflyt' in x for x in r['libraries'])
  assert 'CUDA_MPS_PIPE_DIRECTORY' not in r['environment']
 save(out/'ownership.json',[{'process':p.s.name,'namespace':p.s.ns,'pod_uid':p.s.uid,'ready':p.ready,'host':identities[i]} for i,p in enumerate(probes)])
 save(out/'status.json',{'state':'OWN_CONTROL_AND_MAPPING_QUERIES','utc':time.time()})
 for p in probes:
  assert p.ready['gpu']==GPU and p.ready['mapping_base']==p.ready['address']
  check(p)
  for op in ['read','write','read']:
   r=command(p,op,'access');assert all(r[x]==0 for x in ['prep','launch','sync','copy']) and r['observed']==r['expected'],r
   for peer in probes:check(peer)
 mappings=[]
 for p,target in [(probes[0],probes[1]),(probes[1],probes[0])]:
  own=command(p,'mapping '+str(p.ready['address']),'mapping');assert own['code']==0 and own['own_buffer_alias']
  other=command(p,'mapping '+str(target.ready['address']),'mapping')
  mappings.append({'requester':p.s.name,'owner':target.s.name,'own':own,'peer':other})
  for peer in probes:check(peer)
 save(out/'mapping-queries.json',mappings)
 inventory=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']);(out/'gpu-processes.txt').write_text(inventory)
 for row in identities:assert any(GPU in line and str(row['host_pid'])==line.split(',')[1].strip() for line in inventory.splitlines())
 for p in probes:
  p.close();assert p.p.returncode==0,p.p.returncode
 probes=[]
 save(out/'result.json',{'status':'PASS_NATIVE_PREPARATION','sessions':[s.name for s in sessions],'own_kernel_operations':6,
  'mapping_queries':mappings,'gpu_cross_access_executed':False,'vmweave_end_to_end_test':False,
  'limitation':'Native CUDA/HAMi control only. Failed address-range query is not proof of GPU read/write denial or exhaustive unmapped-address evidence.'})
 print('PASS_NATIVE_PREPARATION',flush=True)
except Exception as e:
 failure=repr(e);save(out/'failure.json',{'error':failure,'utc':time.time()});print('FAILED',failure,flush=True)
finally:
 errors=[]
 for p in probes:
  try:p.close()
  except Exception as e:errors.append(repr(e))
 for s in sessions:
  try:s.close()
  except Exception as e:errors.append(repr(e))
 save(out/'status.json',{'state':'CLOSED' if not errors else 'CLEANUP_ERROR','failure':failure,'cleanup_errors':errors,'utc':time.time()})
 print('CLOSED',errors,flush=True)
 if failure or errors:sys.exit(1)
