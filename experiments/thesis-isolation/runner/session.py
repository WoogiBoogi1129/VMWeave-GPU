"""Fresh VMWeave allocations and processes, drained by UID after each session."""
import gzip, hashlib, shutil, sys, threading
from common import *
CHAN='sharedmemorychannels.vmweave.io'
IMAGES=json.loads((BASE/'images.json').read_text()) if (BASE/'images.json').exists() else {}

class Session:
 def __init__(self,name,path='S',cap=50,slot='a',memory=2048):
  self.memory=memory;self.ns='vmweave-test-'+slot
  self.name=name;self.path=path;self.cap=cap;self.slot=slot;self.out=OUT/'runs'/name
  self.out.mkdir(parents=True,exist_ok=False);self.uid=None;self.ssh=None
  self.art=BASE/'artifacts';self.offset=0
 def get(self,kind,name):return get(kind,name,ns=self.ns)
 def prepare(self):
  if self.path=='N':
   obj={'apiVersion':'v1','kind':'Pod','metadata':{'name':self.name,'namespace':self.ns,'labels':{'vmweave.io/campaign':'performance-20260930'},'annotations':{'nvidia.com/use-gpuuuid':GPU}},
    'spec':{'restartPolicy':'Never','terminationGracePeriodSeconds':1,'automountServiceAccountToken':False,'runtimeClassName':'nvidia','schedulerName':'hami-scheduler','nodeSelector':{'kubernetes.io/hostname':'gpu-4'},
    'containers':[{'name':'native','image':IMAGES['worker'],'command':['sleep','14400'],'resources':{'limits':{'nvidia.com/gpu':1,'nvidia.com/gpumem':4096,'nvidia.com/gpucores':self.cap}},'volumeMounts':[{'name':'art','mountPath':'/evidence'}]}],
    'volumes':[{'name':'art','hostPath':{'path':str(self.art),'type':'Directory'}}]}}
   self.uid=create(obj)['metadata']['uid'];wait(lambda:self.get('pod',self.name).get('status',{}).get('phase')=='Running');self.worker=self.name
   save(self.out/'identity.json',{'path':self.path,'cap':self.cap,'gpu_uuid':GPU,'pod_uid':self.uid,'pod':self.get('pod',self.name)})
   return
  directory='/var/lib/vmweave/thesis-isolation-20261012/'+self.name
  admin(['mkdir','-p','/host'+directory]);admin(['chown','107:107','/host'+directory])
  create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':self.name},'spec':{'capacity':{'storage':'1Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':self.ns,'name':self.name},'local':{'path':directory},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
  create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':self.name,'namespace':self.ns},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':self.name,'resources':{'requests':{'storage':'1Gi'}}}})
  profile='isolation-'+str(self.cap)+'-'+str(self.memory)
  if not self.get('gpuprofiles.vmweave.io',profile):
   create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':profile,'namespace':self.ns},'spec':{'approved':True,'nodeName':'gpu-4','gpuUUID':GPU,'cores':self.cap,'memoryMiB':self.memory,'maxClients':1,'hamiNamespace':'kube-system','schedulerName':'hami-scheduler','runtimeClass':'nvidia','workerImage':IMAGES['worker']}})
  vm={'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':self.name,'namespace':self.ns},'spec':{'runStrategy':'Halted','template':{'spec':{'nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'domain':{'cpu':{'cores':8},'resources':{'requests':{'memory':'16Gi'}},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{}}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','containerDisk':{'image':GUEST}},{'name':'cloudinit','cloudInitNoCloud':{'userData':'#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+(self.art/'guest-key.pub').read_text().strip()+'\n'}}]}}}}
  create(vm)
  call([sys.executable,ROOT/'scripts/operator/create-channel.py','--namespace',self.ns,'--vm',self.name,'--profile',profile,'--pvc',self.name,'--name',self.name,'--compute',self.cap,'--memory',str(self.memory)+'Mi','--helper-image',IMAGES['helper'],'--hook-image',IMAGES['hook']])
  self.uid=self.get(CHAN,self.name)['metadata']['uid']
  wait(lambda:self.get(CHAN,self.name).get('status',{}).get('phase')=='BackingReady')
  k('patch','vm',self.name,'-n',self.ns,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
  def running():
   v=self.get('vmi',self.name)
   return v if v and v.get('status',{}).get('phase')=='Running' and v['status'].get('interfaces') else None
  v=wait(running);self.ip=v['status']['interfaces'][0]['ipAddress']
  self.ssh=['ssh','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts'),'ubuntu@'+self.ip]
  def sshready():
   try:return subprocess.run(self.ssh+['true'],capture_output=True,timeout=8).returncode==0
   except subprocess.TimeoutExpired:return False
  wait(sshready)
  call(self.ssh+['sudo timedatectl set-ntp false'])
  (self.out/'guest-clock-policy.txt').write_text(call(self.ssh+['timedatectl status']))
  channel=self.get(CHAN,self.name);save(self.out/'channel-bound.json',channel)
  self.bdf=call(self.ssh+["python3 -c \"from pathlib import Path; print(next(p.name for p in Path('/sys/bus/pci/devices').iterdir() if (p/'vendor').read_text().strip()=='0x1af4' and (p/'device').read_text().strip()=='0x1110'))\""]).strip()
  call([sys.executable,ROOT/'scripts/export-shm-guest.py','--channel-json',self.out/'channel-bound.json','--bdf',self.bdf,'--slot','0','--output',self.out/'guest-config'])
  self.scp=['scp','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts')]
  call(self.ssh+['mkdir -p /tmp/perf'])
  call(self.scp+[str(self.art/f) for f in ['libflyt_guest.so','load-S','probe-S','work.ptx','isolation']]+[str(self.out/'guest-config/layout.bin'),'ubuntu@'+self.ip+':/tmp/perf/'])
  pods=json.loads(k('get','pods','-n',self.ns,'-o','json'))['items']
  owned=[p for p in pods if any(r.get('uid')==self.uid for r in p['metadata'].get('ownerReferences',[])) and p['metadata']['name'].endswith('-worker')]
  self.worker=owned[0]['metadata']['name'];launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+self.name+'-'))
  affinity=(ROOT/'experiments/evidence/campaign_affinity.py').read_text()
  for pod,cpus in [(launcher,'32-39' if self.slot=='a' else '40-47'),(owned[0],'48-51' if self.slot=='a' else '52-55')]:
   result=k('exec','-i','-n','vmweave-test-a',HELPER,'--','chroot','/host','python3','-',pod['metadata']['uid'],cpus,input=affinity)
   (self.out/(pod['metadata']['name']+'-affinity.json')).write_text(result)
  clocks=[]
  for _ in range(5):
   t0=time.time();g=float(call(self.ssh+['date +%s.%N']));t1=time.time();clocks.append({'before':t0,'guest':g,'after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
  self.offset=min(clocks,key=lambda x:x['uncertainty'])['offset'];save(self.out/'clock-map.json',clocks)
  save(self.out/'identity.json',{'path':self.path,'cap':self.cap,'gpu_uuid':GPU,'channel_uid':self.uid,'worker':self.worker,'worker_uid':owned[0]['metadata']['uid'],'launcher_uid':launcher['metadata']['uid'],'vm_ip':self.ip,'clock_offset':self.offset,'images':IMAGES})
 def command(self,program,args):
  if self.path=='N':return ['kubectl','exec','-n',self.ns,self.name,'--','taskset','-c','0-7','/evidence/'+program,*map(str,args)]
  return self.ssh+['sudo env FLYT_TRACE_REQUESTS=0 FLYT_MIRROR_DEVICE_VA=1 PERF_HOLD_UNTIL_UTC='+str(getattr(self,'hold_until',0))+' FLYT_LAYOUT=/tmp/perf/layout.bin FLYT_IVSHMEM_BDF='+self.bdf+' FLYT_SLOT=0 LD_LIBRARY_PATH=/tmp/perf /tmp/perf/'+program+' '+shlex.join(list(map(str,args)))]
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
   current=self.get(CHAN,self.name)
   if current['metadata']['uid']!=self.uid:raise RuntimeError('Channel UID changed')
   if getattr(self,'worker',None):
    (self.out/'worker-output.txt').write_text(k('logs','-n',self.ns,self.worker,check=False))
   k('patch',CHAN,self.name,'-n',self.ns,'--type=json','-p',json.dumps([{'op':'test','path':'/metadata/uid','value':self.uid},{'op':'add','path':'/spec/drain','value':True}]))
   released=wait(lambda:(c if (c:=self.get(CHAN,self.name)).get('status',{}).get('phase')=='Released' else None))
   save(self.out/'channel-released.json',released)
  else:
   if self.get('pod',self.name)['metadata']['uid']!=self.uid:raise RuntimeError('Pod UID changed')
   k('delete','pod',self.name,'-n',self.ns,'--wait=true','--timeout=90s')
  save(self.out/'cleanup.json',{'released':True,'uid':self.uid,'utc':time.time()})
