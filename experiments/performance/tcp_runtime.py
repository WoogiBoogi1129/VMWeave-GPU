"""Dedicated legacy Flyt TCP/MPS session; configuration lives outside Git."""
import json,subprocess,time
from pathlib import Path
from common import NS,GPU,GUEST,OUT,HELPER,save,wait
import common
def k(args, **kw):return common.k(*args, **kw)
get=common.get
call=common.call
TCP_NS='vmweave-performance-tcp'
def vget(kind,name):
 s=k(['get',kind,name,'-n',TCP_NS,'--ignore-not-found','-o','json']);return json.loads(s) if s.strip() else None
class TCP:
 def __init__(self,base,name):
  self.base=Path(base).resolve();self.name=name;self.out=OUT/'runs'/name;self.out.mkdir(parents=True,exist_ok=False);self.art=self.base/'artifacts';self.uid=None;self.vmi_uid=None;self.path='T';self.cap=100;self.offset=0
 def prepare(self):
  legacy=json.loads((self.base/'legacy.json').read_text());cfg=self.base/'legacy-config';self.worker=self.name+'-cell'
  # Original manager retains disconnected GPU inventories. Reset ONLY this
  # campaign's isolated manager/Mongo Pod before each independent session.
  old=get('pod','perf-tcp-manager')
  if old['metadata']['uid']!=legacy['manager_uid']:raise RuntimeError('manager UID changed')
  (self.out/'previous-manager.log').write_text(k(['logs','-n',NS,'perf-tcp-manager','-c','manager']))
  k(['delete','pod','perf-tcp-manager','-n',NS,'--wait=true','--timeout=90s'])
  original=json.loads((self.base/'private-manager.json').read_text())
  original={'apiVersion':'v1','kind':'Pod','metadata':{'name':'perf-tcp-manager','namespace':NS},'spec':original['spec']}
  created=json.loads(k(['create','-f','-','-o','json'],input=json.dumps(original)))
  wait(lambda:get('pod','perf-tcp-manager').get('status',{}).get('phase')=='Running',300)
  ip=get('pod','perf-tcp-manager')['status']['podIP']
  for name in ['node-mgr.toml','client-mgr.toml']:
   f=cfg/name;f.write_text(f.read_text().replace(legacy['manager_ip'],ip))
  legacy.update({'manager_ip':ip,'manager_uid':created['metadata']['uid']});save(self.base/'legacy.json',legacy)
  time.sleep(16)

  pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':self.worker,'namespace':NS},'spec':{'nodeName':'gpu-4','runtimeClassName':'nvidia','restartPolicy':'Never','terminationGracePeriodSeconds':5,'automountServiceAccountToken':False,'containers':[{'name':'cell','image':legacy['cell_image'],'command':['taskset','-c','16-19','/usr/local/bin/flyt-gpu-cell-entrypoint'],'env':[{'name':n,'value':v} for n,v in {'NVIDIA_VISIBLE_DEVICES':'k8s.device-plugin.nvidia.com/gpu='+GPU,'NVIDIA_DRIVER_CAPABILITIES':'compute,utility','FLYT_ALLOWED_GPU_UUIDS':GPU,'FLYT_NODE_MANAGER_CONFIG':'/etc/flyt/node-mgr.toml','RUST_LOG':'info'}.items()],'volumeMounts':[{'name':'cfg','mountPath':'/etc/flyt','readOnly':True},{'name':'shm','mountPath':'/dev/shm'}]}],'volumes':[{'name':'cfg','hostPath':{'path':str(cfg),'type':'Directory'}},{'name':'shm','emptyDir':{'medium':'Memory','sizeLimit':'2Gi'}}]}}
  pod['spec']['volumes'] += [{'name':'mps-run','emptyDir':{}},{'name':'mps-log','emptyDir':{}}]
  pod['spec']['containers'][0]['volumeMounts'] += [{'name':'mps-run','mountPath':'/run/flyt-mps'},{'name':'mps-log','mountPath':'/var/log/flyt-mps'}]
  self.uid=json.loads(k(['create','-f','-','-o','json'],input=json.dumps(pod)))['metadata']['uid'];save(self.out/'cell-manifest.json',pod)
  def running():
   current=get('pod',self.worker)
   if not current or current.get('status',{}).get('phase')=='Failed':raise RuntimeError('TCP cell failed; inspect preserved log')
   return current.get('status',{}).get('phase')=='Running'
  wait(running,300)
  self.server_ip=get('pod',self.worker)['status']['podIP']
  key=(self.art/'guest-key.pub').read_text().strip()
  vm={'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':self.name,'namespace':NS},'spec':{'runStrategy':'Always','template':{'spec':{'nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'domain':{'cpu':{'cores':8},'resources':{'requests':{'memory':'16Gi'}},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{}}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','containerDisk':{'image':GUEST}},{'name':'cloudinit','cloudInitNoCloud':{'userData':'#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+key+'\nssh_pwauth: false\n'}}]}}}}
  vm['metadata']['namespace']=TCP_NS
  self.vm_uid=json.loads(k(['create','-f','-','-o','json'],input=json.dumps(vm)))['metadata']['uid']
  def readyvm():
   v=vget('vmi',self.name);return v if v and v.get('status',{}).get('phase')=='Running' and v['status'].get('interfaces') else None
  v=wait(readyvm);self.vmi_uid=v['metadata']['uid'];self.ip=v['status']['interfaces'][0]['ipAddress']
  self.ssh=['ssh','-i',str(self.art/'guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts'),'ubuntu@'+self.ip]
  wait(lambda:subprocess.run(self.ssh+['true'],capture_output=True,timeout=8).returncode==0)
  call(self.ssh+['sudo timedatectl set-ntp false'])
  (self.out/'guest-clock-policy.txt').write_text(call(self.ssh+['timedatectl status']))
  pods=json.loads(k(['get','pods','-n',TCP_NS,'-o','json']))['items'];p=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+self.name+'-'));self.launcher=p['metadata']['name']
  affinity=(Path(__file__).parent.parent/'evidence/campaign_affinity.py').read_text();(self.out/'cpu-pinning.txt').write_text(k(['exec','-i','-n',NS,HELPER,'--','python3','-',p['metadata']['uid'],'0-7'],input=affinity))
  call(self.ssh+['mkdir -p /tmp/perf; sudo mkdir -p /etc/flyt'])
  scp=['scp','-i',str(self.art/'guest-key'),'-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.out/'known-hosts')]
  self.scp=scp
  files=[self.art/x for x in ['probe-T','cricket-client.so','flyt-client-manager','libtirpc.so.3.0.0','work.cubin']]+[cfg/'client-mgr.toml']
  call(scp+[str(f) for f in files]+['ubuntu@'+self.ip+':/tmp/perf/'])
  # Library dependencies from guest image are checked before starting the manager.
  (self.out/'guest-dependencies.txt').write_text(call(self.ssh+['ldd /tmp/perf/cricket-client.so; ldd /tmp/perf/flyt-client-manager']))
  # Query actual physical SM count from the legacy node manager's GPU inventory log.
  log=k(['logs','-n',NS,self.worker]);(self.out/'cell-start.log').write_text(log)
  # Full Blackwell GPU: derive from driver outside timed windows, never assume old 92-SM defaults.
  info=k(['exec','-n',NS,self.worker,'--','nvidia-smi','--query-gpu=name,uuid,memory.total','--format=csv,noheader']);(self.out/'gpu.txt').write_text(info)
  seed='const c=db.getSiblingDB("flyt").vm_required_resources;c.updateOne({vm_ip:'+json.dumps(self.ip)+'},{$set:{vm_ip:'+json.dumps(self.ip)+',host_ip:'+json.dumps(self.server_ip)+',compute_units:142,memory:4096}},{upsert:true});printjson(c.findOne({vm_ip:'+json.dumps(self.ip)+'},{_id:0}));'
  # SM count is filled by caller from the verified CUDA capability probe.
  sm=int((self.base/'sm-count.txt').read_text());seed=seed.replace('compute_units:142','compute_units:'+str(sm));self.sm=sm
  cmd=['/bin/sh','-c','exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "$1"','sh',seed]
  (self.out/'resource-seed.txt').write_text(k(['exec','-n',NS,'perf-tcp-manager','-c','mongo','--',*cmd]))
  call(self.ssh+['ln -sf libtirpc.so.3.0.0 /tmp/perf/libtirpc.so.3; ln -sf cricket-client.so /tmp/perf/libcudart.so.12; sudo cp /tmp/perf/client-mgr.toml /etc/flyt/client-mgr.toml; sudo sh -c "nohup env LD_LIBRARY_PATH=/tmp/perf RUST_LOG=info /tmp/perf/flyt-client-manager >/tmp/perf/manager.log 2>&1 </dev/null &"'])
  clocks=[]
  for _ in range(5):
   t0=time.time();g=float(call(self.ssh+['date +%s.%N']));t1=time.time();clocks.append({'before':t0,'guest':g,'after':t1,'offset':g-(t0+t1)/2,'uncertainty':(t1-t0)/2})
  self.offset=min(clocks,key=lambda x:x['uncertainty'])['offset'];save(self.out/'clock-map.json',clocks)
  save(self.out/'identity.json',{'path':'T','cell_uid':self.uid,'cell_ip':self.server_ip,'vm_ip':self.ip,'vmi_uid':self.vmi_uid,'launcher_uid':p['metadata']['uid'],'gpu_uuid':GPU,'sm_count':sm,'memory_mib':4096,'cell_image':legacy['cell_image'],'guest_cpu_set':'0-7','server_cpu_set':'16-19','transport':'TCP between distinct VM and server pod IPs; no shared host filesystem','policy':'MPS full physical SM count','clock_offset':self.offset})
 def close(self):
  if self.vmi_uid:
   vm=vget('vm',self.name)
   if vm and vm['metadata']['uid']==self.vm_uid:k(['patch','vm',self.name,'-n',TCP_NS,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}']);wait(lambda:not vget('vmi',self.name),180)
  if self.uid:
   p=get('pod',self.worker)
   if p and p['metadata']['uid']==self.uid:
    (self.out/'cell.log').write_text(k(['logs','-n',NS,self.worker]));k(['delete','pod',self.worker,'-n',NS,'--wait=true','--timeout=90s'])
  save(self.out/'cleanup.json',{'released':True,'cell_uid':self.uid,'vmi_uid':self.vmi_uid,'utc':time.time()})
