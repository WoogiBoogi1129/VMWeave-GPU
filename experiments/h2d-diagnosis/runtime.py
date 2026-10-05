"""Fresh VMWeave allocations and processes, drained by UID after each session."""
import gzip, hashlib, shutil, sys, threading
from common import *
CHAN='sharedmemorychannels.vmweave.io'
IMAGES=json.loads((BASE/'images.json').read_text()) if (BASE/'images.json').exists() else {}

class Session:
 def __init__(self,name,path='S',cap=100,slot='a'):
  self.name=name;self.path=path;self.cap=cap;self.slot=slot;self.out=OUT/'runs'/name
  self.out.mkdir(parents=True,exist_ok=False);self.uid=None;self.ssh=None
  self.art=BASE/'artifacts';self.offset=0
 def prepare(self):
  if self.path=='N':
   obj={'apiVersion':'v1','kind':'Pod','metadata':{'name':self.name,'namespace':NS,'labels':{'vmweave.io/campaign':'h2d-diagnosis-20261005'},'annotations':{'nvidia.com/use-gpuuuid':GPU}},
    'spec':{'restartPolicy':'Never','terminationGracePeriodSeconds':1,'automountServiceAccountToken':False,'runtimeClassName':'nvidia','schedulerName':'hami-scheduler','nodeSelector':{'kubernetes.io/hostname':'gpu-4'},
    'containers':[{'name':'native','image':IMAGES['worker'],'command':['sleep','14400'],'resources':{'limits':{'nvidia.com/gpu':1,'nvidia.com/gpumem':4096,'nvidia.com/gpucores':self.cap}},'volumeMounts':[{'name':'art','mountPath':'/evidence'}]}],
    'volumes':[{'name':'art','hostPath':{'path':str(self.art),'type':'Directory'}}]}}
   self.uid=create(obj)['metadata']['uid'];wait(lambda:get('pod',self.name).get('status',{}).get('phase')=='Running');self.worker=self.name
   save(self.out/'identity.json',{'path':self.path,'cap':self.cap,'gpu_uuid':GPU,'pod_uid':self.uid,'pod':get('pod',self.name)})
   return
  directory='/var/lib/vmweave/h2d-diagnosis-20261005/'+self.name
  admin(['mkdir','-p','/host'+directory]);admin(['chown','107:107','/host'+directory])
  create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':self.name},'spec':{'capacity':{'storage':'1Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':NS,'name':self.name},'local':{'path':directory},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
  create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':self.name,'namespace':NS},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':self.name,'resources':{'requests':{'storage':'1Gi'}}}})
  profile='scprofile-'+self.name
  if not get('gpuprofiles.vmweave.io',profile):
   create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':profile,'namespace':NS},'spec':{'approved':True,'nodeName':'gpu-4','gpuUUID':GPU,'cores':self.cap,'memoryMiB':4096,'maxClients':1,'hamiNamespace':'kube-system','schedulerName':'hami-scheduler','runtimeClass':'nvidia','workerImage':IMAGES['worker']}})
  vm={'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':self.name,'namespace':NS},'spec':{'runStrategy':'Halted','template':{'spec':{'nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'domain':{'cpu':{'cores':8},'resources':{'requests':{'memory':'16Gi'}},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{}}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','containerDisk':{'image':GUEST}},{'name':'cloudinit','cloudInitNoCloud':{'userData':'#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+(self.art/'guest-key.pub').read_text().strip()+'\n'}}]}}}}
  create(vm)
  call([sys.executable,ROOT/'scripts/operator/create-channel.py','--namespace',NS,'--vm',self.name,'--profile',profile,'--pvc',self.name,'--name',self.name,'--compute',self.cap,'--memory','4096Mi','--helper-image',IMAGES['helper'],'--hook-image',IMAGES['hook']])
  self.uid=get(CHAN,self.name)['metadata']['uid']
  wait(lambda:get(CHAN,self.name).get('status',{}).get('phase')=='BackingReady')
  k('patch','vm',self.name,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
  def running():
   v=get('vmi',self.name)
   return v if v and v.get('status',{}).get('phase')=='Running' and v['status'].get('interfaces') else None
  v=wait(running);self.ip=v['status']['interfaces'][0]['ipAddress']
  self.ssh=['ssh','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts'),'ubuntu@'+self.ip]
  def sshready():
   try:return subprocess.run(self.ssh+['true'],capture_output=True,timeout=8).returncode==0
   except subprocess.TimeoutExpired:return False
  wait(sshready)
  call(self.ssh+['sudo timedatectl set-ntp false'])
  (self.out/'guest-clock-policy.txt').write_text(call(self.ssh+['timedatectl status']))
  channel=get(CHAN,self.name);save(self.out/'channel-bound.json',channel)
  self.bdf=call(self.ssh+["python3 -c \"from pathlib import Path; print(next(p.name for p in Path('/sys/bus/pci/devices').iterdir() if (p/'vendor').read_text().strip()=='0x1af4' and (p/'device').read_text().strip()=='0x1110'))\""]).strip()
  call([sys.executable,ROOT/'scripts/export-shm-guest.py','--channel-json',self.out/'channel-bound.json','--bdf',self.bdf,'--slot','0','--output',self.out/'guest-config'])
  self.scp=['scp','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts')]
  call(self.ssh+['mkdir -p /tmp/perf'])
  call(self.scp+[str(self.art/f) for f in ['libflyt_guest.so','load-S','probe-S','work.ptx']]+[str(self.out/'guest-config/layout.bin'),'ubuntu@'+self.ip+':/tmp/perf/'])
  (self.out/'guest-artifact-hashes.txt').write_text(call(self.ssh+['sha256sum /tmp/perf/libflyt_guest.so /tmp/perf/probe-S /tmp/perf/work.ptx']))
  pods=json.loads(k('get','pods','-n',NS,'-o','json'))['items']
  owned=[p for p in pods if any(r.get('uid')==self.uid for r in p['metadata'].get('ownerReferences',[])) and p['metadata']['name'].endswith('-worker')]
  self.worker=owned[0]['metadata']['name'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+self.name+'-'))
  wait(lambda:get('pod',self.worker).get('status',{}).get('phase')=='Running')
  affinity=(ROOT/'experiments/evidence/campaign_affinity.py').read_text()
  for pod,cpus in [(launcher,'0-7' if self.slot=='a' else '8-15'),(owned[0],'16-19' if self.slot=='a' else '20-23')]:
   result=k('exec','-i','-n',NS,HELPER,'--','python3','-',pod['metadata']['uid'],cpus,input=affinity)
   (self.out/(pod['metadata']['name']+'-affinity.json')).write_text(result)
  clocks=[]
  for _ in range(5):
   t0=time.time();g=float(call(self.ssh+['date +%s.%N']));t1=time.time();clocks.append({'before':t0,'guest':g,'after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
  self.offset=min(clocks,key=lambda x:x['uncertainty'])['offset'];save(self.out/'clock-map.json',clocks)
  save(self.out/'identity.json',{'path':self.path,'cap':self.cap,'gpu_uuid':GPU,'channel_uid':self.uid,'worker':self.worker,'worker_uid':owned[0]['metadata']['uid'],'launcher_uid':launcher['metadata']['uid'],'vm_ip':self.ip,'clock_offset':self.offset,'images':IMAGES})
 def command(self,program,args):
  if self.path=='N':return ['kubectl','exec','-n',NS,self.name,'--','taskset','-c','0-7','/evidence/'+program,*map(str,args)]
  return self.ssh+['sudo env FLYT_TRACE_REQUESTS=0 PERF_HOLD_UNTIL_UTC='+str(getattr(self,'hold_until',0))+' FLYT_LAYOUT=/tmp/perf/layout.bin FLYT_IVSHMEM_BDF='+self.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/perf /tmp/perf/'+program+' '+shlex.join(list(map(str,args)))]
 @classmethod
 def resume_premeasurement(cls,name):
  s=cls.__new__(cls);s.name=name;s.path='S';s.cap=100;s.slot='a';s.art=BASE/'artifacts';s.out=OUT/'runs'/name;s.offset=0
  assert not (s.out/'command.json').exists() and not (s.out/'execution.json').exists(), 'Never repeat a measured attempt'
  original=json.loads((s.out/'channel-bound.json').read_text());channel=get(CHAN,name);s.uid=original['metadata']['uid'];assert channel['metadata']['uid']==s.uid
  v=get('vmi',name);assert v['status']['phase']=='Running';s.ip=v['status']['interfaces'][0]['ipAddress']
  s.ssh=['ssh','-i',str(s.art/'guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(s.out/'known-hosts'),'ubuntu@'+s.ip]
  s.scp=['scp','-i',str(s.art/'guest-key'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(s.out/'known-hosts')]
  s.bdf=call(s.ssh+["python3 -c \"from pathlib import Path; print(next(p.name for p in Path('/sys/bus/pci/devices').iterdir() if (p/'vendor').read_text().strip()=='0x1af4' and (p/'device').read_text().strip()=='0x1110'))\""]).strip()
  pods=json.loads(k('get','pods','-n',NS,'-o','json'))['items'];worker=next(p for p in pods if p['metadata']['name'].endswith('-worker') and any(r.get('uid')==s.uid for r in p['metadata'].get('ownerReferences',[])))
  s.worker=worker['metadata']['name'];wait(lambda:get('pod',s.worker)['status']['phase']=='Running')
  launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+name+'-'))
  for pod,cpus in [(launcher,'0-7'),(worker,'16-19')]:
   result=k('exec','-i','-n',NS,HELPER,'--','python3','-',pod['metadata']['uid'],cpus,input=(ROOT/'experiments/evidence/campaign_affinity.py').read_text())
   (s.out/(pod['metadata']['name']+'-affinity.json')).write_text(result)
  clocks=[]
  for _ in range(5):
   t0=time.time();g=float(call(s.ssh+['date +%s.%N']));t1=time.time();clocks.append({'before':t0,'guest':g,'after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
  s.offset=min(clocks,key=lambda x:x['uncertainty'])['offset'];save(s.out/'clock-map.json',clocks)
  save(s.out/'identity.json',{'path':'S','cap':100,'gpu_uuid':GPU,'channel_uid':s.uid,'worker':s.worker,'worker_uid':worker['metadata']['uid'],'launcher_uid':launcher['metadata']['uid'],'vm_ip':s.ip,'clock_offset':s.offset,'images':IMAGES})
  save(s.out/'preparation-resume.json',{'utc':time.time(),'reason':'Node image GC removed local Worker image before first workload; restored exact image and retained stopped references. No measurement was restarted.','channel_uid':s.uid})
  return s
 def execute(self,kind='load',seconds=120,warmup=30,reps=524288,count=0,start=0,hold_until=0):
  self.hold_until=hold_until+self.offset if hold_until else 0
  prefix=('/evidence/' if self.path=='N' else '/tmp/perf/')+self.name
  directory='/evidence/' if self.path=='N' else '/tmp/perf/'
  args=[seconds,warmup,reps,count,start+self.offset if start else 0,prefix,directory+'work.ptx'] if kind=='load' else ['batch',10,30,10,prefix,directory+'work.ptx',0,127]
  cmd=self.command(('load-' if kind=='load' else 'probe-')+self.path,args)
  return execute_stream(self,cmd,prefix)
 def close(self):
  if not self.uid:return
  if self.path=='S':
   current=get(CHAN,self.name)
   if current['metadata']['uid']!=self.uid:raise RuntimeError('Channel UID changed')
   if getattr(self,'worker',None):
    output=k('logs','-n',NS,self.worker,check=False)
    if output or not (self.out/'worker-output.txt').exists():(self.out/'worker-output.txt').write_text(output)
   k('patch',CHAN,self.name,'-n',NS,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':self.uid},{'op':'add','path':'/spec/drain','value':True}]))
   released=wait(lambda:(c if (c:=get(CHAN,self.name)).get('status',{}).get('phase')=='Released' else None))
   save(self.out/'channel-released.json',released)
  else:
   if get('pod',self.name)['metadata']['uid']!=self.uid:raise RuntimeError('Pod UID changed')
   k('delete','pod',self.name,'-n',NS,'--wait=true','--timeout=90s')
  save(self.out/'cleanup.json',{'released':True,'uid':self.uid,'utc':time.time()})

STATE_LOCK=threading.Lock()
def record_state(session,row):
 with STATE_LOCK:
  p=BASE/'live-state.json';states=json.loads(p.read_text()) if p.exists() else {}
  states[session.name]={'cap':session.cap,'path':session.path,'updated':time.time(),**row}
  tmp=p.with_suffix('.tmp');save(tmp,states);tmp.replace(p)

def execute_stream(s,cmd,prefix):
 save(s.out/'command.json',{'argv':cmd,'utc':time.time()});print('COMMAND',s.name,shlex.join(cmd),flush=True)
 results=[];snapshot=False;collected=False
 with (s.out/'stdout.jsonl').open('w') as out,(s.out/'stderr.txt').open('w') as err:
  p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True);timer=threading.Timer(1800,p.kill);timer.start()
  try:
   for line in p.stdout:
    out.write(line);out.flush()
    try:row=json.loads(line)
    except ValueError:continue
    record_state(s,row)
    if row.get('event')=='ARTIFACTS_READY':
     collect_artifacts(s,prefix,results,0);collected=True
     call(s.ssh+['touch '+shlex.quote(prefix+'.collected')])
    if row.get('event')!='TICK':print(s.name,line.strip(),flush=True)
    if row.get('event')=='RESULT':results.append(row)
    if row.get('event')=='WARMUP_START' and not snapshot:
     pod=get('pod',s.worker);source=(ROOT/'experiments/h2d-diagnosis/read_runtime.py').read_text()
     (s.out/'runtime-libraries.json').write_text(k('exec','-i','-n',NS,HELPER,'--','python3','-',pod['metadata']['uid'],input=source))
     runtime=json.loads((s.out/'runtime-libraries.json').read_text())
     expected=getattr(s,'worker_hash',hashlib.sha256((BASE/'artifacts/bin/flyt-shm-worker').read_bytes()).hexdigest())
     if s.path=='S' and (not runtime or any(r['executable_sha256']!=expected for r in runtime)):
      raise RuntimeError('Worker binary differs from measured build')
     if s.path in ['N','S']:
      if not runtime or not all(r['environment'].get('GPU_CORE_UTILIZATION_POLICY')=='FORCE' and r['environment'].get('CUDA_DEVICE_SM_LIMIT')==str(s.cap) and any('libvgpu' in f for f in r['library_hashes']) for r in runtime):raise RuntimeError('Runtime policy/library does not match requested cap')
     if s.path=='T':
      (s.out/'tcp-connections.txt').write_text(call(s.ssh+['ss -tnp; ip -brief address']))
      if any('libvgpu' in f for r in runtime for f in r['library_hashes']):raise RuntimeError('Unexpected HAMi injection in TCP baseline')
     if s.path=='S':save(s.out/'channel-running.json',get(CHAN,s.name))
     snapshot=True
   code=p.wait()
  finally:
   timer.cancel()
   if p.poll() is None:p.kill();p.wait()
 save(s.out/'execution.json',{'exit_code':code,'results':results,'ended_utc':time.time()})
 if not collected:collect_artifacts(s,prefix,results,code)
 # Shared jobs can finish long before their peer. Preserve logs immediately,
 # before a controller removes the terminated Worker Pod.
 if s.path=='S':
  output=k('logs','-n',NS,s.worker,check=False)
  if output:(s.out/'worker-output.txt').write_text(output)
 if code or not results or any(r.get('status')!='PASS' for r in results):raise RuntimeError('Invalid workload '+s.name)
 return results

def collect_artifacts(s,prefix,results,code):
 if s.path=='N':files=list(s.art.glob(s.name+'-*.csv'))
 else:
  incoming=BASE/'incoming'/s.name;incoming.mkdir(parents=True,exist_ok=True)
  call(s.scp+['ubuntu@'+s.ip+':'+prefix+'-*.csv',str(incoming)],timeout=300,check=code==0)
  files=list(incoming.glob('*.csv'))
 for file in files:
  with file.open('rb') as f,gzip.open(s.out/(file.name+'.gz'),'wb') as g:shutil.copyfileobj(f,g)
 # Independently verify persisted final buffers outside timed windows.
 if s.path in ['S','T'] and results and all(r.get('mode') in ['copy','h2d'] for r in results):
  import array
  hashes=call(s.ssh+['sha256sum '+shlex.quote(prefix)+'*.output.bin'])
  checked=[]
  for line in hashes.splitlines():
   digest,file=line.split(maxsplit=1)
   match=next((r for r in results if file.endswith('-'+r['mode']+'-'+str(r['bytes'])+'.output.bin')),None)
   if match is None and len(results)==1:match=results[0]
   if match is None:raise RuntimeError('Unexpected output file '+file)
   values=array.array('I',range(2026,2026+match['bytes']//4))
   if sys.byteorder!='little':values.byteswap()
   expected=hashlib.sha256(values.tobytes()).hexdigest()
   checked.append({'file':file,'bytes':match['bytes'],'sha256':digest,'expected':expected,'pass':digest==expected})
  save(s.out/'output-validation.json',checked)
  if len(checked)!=len(results) or not all(x['pass'] for x in checked):raise RuntimeError('Independent output verification failed')
