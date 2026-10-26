"""Isolated Rodinia campaign. No changes to product implementation."""
import json,subprocess,time,sys,importlib.util,shlex,hashlib
from pathlib import Path
R=Path.cwd();B=R/'.local/bulk-short-20261026';O=R/'experiments/ai-passthrough/results/20261026-bulk-short';NS='vmweave-test-a';ADMIN='bulk-native-admin-1026';GPU='GPU-772181af-05a4-0c24-de59-8487bd37c142';images=json.loads((R/'deploy/releases/v0.5.3.json').read_text())['images'];PUB=R/'.local/v053-rollout-20261025/published-guest'
def k(*a,**kw):return subprocess.check_output(['kubectl',*map(str,a)],text=True,**kw)
def get(kind,name,ns=NS):
 s=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def create(obj):return json.loads(k('create','-f','-','-o','json',input=json.dumps(obj)))
def wait(fn,seconds=300):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if (x:=fn()):return x
  time.sleep(2)
 raise TimeoutError('campaign resource wait')
def save(path,value):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(value,indent=2))
def admin(cmd,**kw):return k('exec','-i','-n',NS,ADMIN,'--','chroot','/host',*cmd,**kw)
def ensure_admin():
 if not get('pod',ADMIN):create({'apiVersion':'v1','kind':'Pod','metadata':{'name':ADMIN,'namespace':NS},'spec':{'nodeName':'gpu-4','hostPID':True,'restartPolicy':'Never','terminationGracePeriodSeconds':1,'automountServiceAccountToken':False,'containers':[{'name':'admin','image':images['worker'],'command':['sleep','43200'],'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}})
 wait(lambda:get('pod',ADMIN).get('status',{}).get('phase')=='Running')
def drop_admin():k('delete','pod',ADMIN,'-n',NS,'--ignore-not-found','--wait=true','--timeout=90s')
def ssh_for(ip, identity=None):
 opts=['-i',str(R/'.local/thesis-isolation-20261012/artifacts/guest-key'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(B/('campaign-known-hosts-'+identity if identity else 'campaign-known-hosts'))]
 ssh=['ssh',*opts,'ubuntu@'+ip];scp=['scp',*opts];wait(lambda:subprocess.run(ssh+['true'],capture_output=True,timeout=8).returncode==0);return ssh,scp
def remote(s,cmd,**kw):return subprocess.check_output(s['ssh']+[cmd],text=True,**kw)
def arm_affinity(label,executor=None):
 config=B/('affinity-'+label+'.json');out=B/('affinity-'+label+'-done.json');assert not config.exists() and not out.exists()
 args=['systemd-run','--unit=rodinia-affinity-'+label,'--collect','--property=RuntimeMaxSec=420','python3',str(B/'affinity-once.py'),str(config),str(out)]
 if executor:executor(args)
 else:admin(args)
 return config,out
def finish_affinity(label,launcher,backend):
 config=B/('affinity-'+label+'.json');out=B/('affinity-'+label+'-done.json')
 save(config,[{'uid':launcher['metadata']['uid'],'cpus':list(range(32,40)),'patterns':['qemu-kvm']},{'uid':backend['metadata']['uid'],'cpus':list(range(40,44)),'patterns':['vmweave-shm-worker','vmweave-shm-session-worker','flyt-node-manager','flyt-cluster-manager','nvidia-cuda-mps']}])
 wait(lambda:out.exists(),30);return out.read_text()
def prepare_vmw(label):
 name='bulk-w-1026-'+label;ensure_admin();directory='/var/lib/vmweave/bulk-short-20261026/'+name
 admin(['mkdir','-p',directory]);admin(['chown','107:107',directory])
 create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':'1Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':NS,'name':name},'local':{'path':directory},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
 create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':NS},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':name,'resources':{'requests':{'storage':'1Gi'}}}})
 create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':name,'namespace':NS},'spec':{'approved':True,'nodeName':'gpu-4','gpuUUID':GPU,'cores':100,'memoryMiB':8192,'maxClients':1,'hamiNamespace':'kube-system','schedulerName':'hami-scheduler','runtimeClass':'nvidia','workerImage':images['worker']}})
 vm=json.loads((O/'flyt-vm.json').read_text())
 # Build a fresh VM, using only the validated machine shape, not old identity/status.
 spec=vm['spec'];spec.pop('nodeName',None);spec.pop('startStrategy',None)
 # Runtime VMI is not a template: take the static template from the Flyt preparation script.
 import ast
 source=(B/'prepare.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='vm' for t in n.targets));vm_source=ast.get_source_segment(source,node)
 env={'NAME':name,'NS':NS,'hook':[],'aid':'','generation':'','key':(R/'.local/thesis-isolation-20261012/artifacts/guest-key.pub').read_text().strip(),'json':json};exec(vm_source,env);vm=env['vm'];vm['spec']['template'].pop('metadata',None);create(vm)
 subprocess.run(['python3',str(R/'scripts/operator/create-channel.py'),'--lifecycle','VM','--namespace',NS,'--vm',name,'--profile',name,'--pvc',name,'--name',name,'--compute','100','--memory','8192Mi','--helper-image',images['helper'],'--hook-image',images['hook']],check=True)
 wait(lambda:get('sharedmemorychannel',name).get('status',{}).get('phase')=='Stopped')
 arm_affinity(name);drop_admin();k('patch','vm',name,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
 v=wait(lambda:x if (x:=get('vmi',name)) and x.get('status',{}).get('phase')=='Running' and (x['status'].get('interfaces') and x['status']['interfaces'][0].get('ipAddress')) else None);ip=v['status']['interfaces'][0]['ipAddress'];ssh,scp=ssh_for(ip,v['metadata']['uid'])
 s={'mode':'vmweave','name':name,'namespace':NS,'ip':ip,'ssh':ssh,'scp':scp,'directory':directory,'vmUID':get('vm',name)['metadata']['uid']};save(B/'active-vmw.json',s)
 subprocess.run(scp+['-r',str(PUB),'ubuntu@'+ip+':/tmp/package'],check=True)
 remote(s,'sudo sh /tmp/package/install_guest_broker.sh /tmp/package && sudo systemctl start vmweave-guest-broker.service')
 wait(lambda:subprocess.run(ssh+['sudo test -S /run/vmweave/gpu.sock'],capture_output=True).returncode==0)
 channel=get('sharedmemorychannel',name);uid=channel['metadata']['uid'];pods=json.loads(k('get','pods','-n',NS,'-o','json'))['items'];worker=next(p for p in pods if p['metadata']['name'].endswith('-worker') and any(o.get('uid')==uid for o in p['metadata'].get('ownerReferences',[])));launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+name+'-'));s['worker']=worker['metadata']['name'];s['channelUID']=uid
 out=O/'identities'/name;out.mkdir(parents=True,exist_ok=True);save(out/'channel.json',channel);save(out/'worker.json',worker);save(out/'vmi.json',v)
 (out/'worker-runtime.sha256').write_text(k('exec','-n',NS,worker['metadata']['name'],'--','sh','-c','sha256sum /usr/local/cuda/lib64/libcudart.so.12'))
 (out/'cpu-affinity.log').write_text(finish_affinity(name,launcher,worker))
 save(B/'active-vmw.json',s);stage(s);return s

def stage(s):
 remote(s,'mkdir -p /tmp/rodinia; sudo timedatectl set-ntp false')
 runtime=R/'.local/thesis-isolation-20261012/bundle-stage/opt/flyt-cuda-libs/libcudart.so.12'
 subprocess.run(s['scp']+[str(B/'needle-timed'),str(B/'lud-timed'),str(B/'needle-diag'),str(B/'lud-diag'),str(runtime),'ubuntu@'+s['ip']+':/tmp/rodinia/'],check=True)

def measure(s,stage,label,workloads=None):
 expected=json.loads((R/'experiments/ai-passthrough/results/20261023-large-copy/rodinia-comparison.json').read_text());rows=[];out=O/stage/label/s['mode'];out.mkdir(parents=True,exist_ok=False)
 gpu_command=['nvidia-smi','-i',GPU,'--query-gpu=uuid,driver_version,pstate,clocks.sm,power.draw,temperature.gpu,memory.used','--format=csv']
 if s['mode']=='passthrough':gpu_command=s['ssh']+['sudo env LD_LIBRARY_PATH=/opt/flyt-evidence/driver /opt/flyt-evidence/driver/nvidia-smi --query-gpu=uuid,driver_version,pstate,clocks.sm,power.draw,temperature.gpu,memory.used --format=csv']
 (out/'gpu-before.csv').write_text(subprocess.check_output(gpu_command,text=True))
 (out/'binaries.sha256').write_text(remote(s,'sha256sum /tmp/rodinia/needle-timed /tmp/rodinia/lud-timed /tmp/rodinia/libcudart.so.12'))
 for name,binary,args in [('nw','needle-timed','2048 10'),('lud2064','lud-timed','-s 2064')]:
  if workloads and name not in workloads:continue
  if stage=='diagnostic':binary=binary.replace('-timed','-diag')
  prefix='/tmp/rodinia/'+name
  env='env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/rodinia:/opt/flyt-evidence/driver' if s['mode']=='passthrough' else 'env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock VMWEAVE_MIRROR_DEVICE_VA=1 VMWEAVE_TRACE_REQUESTS=0 LD_PRELOAD=/opt/vmweave/lib/libvmweave_guest.so LD_LIBRARY_PATH=/opt/vmweave/lib:/tmp/rodinia'
  if s['mode']=='flyt':env='env -u LD_PRELOAD LD_LIBRARY_PATH=/tmp/flyt-test:/tmp/rodinia'
  cmd='mkdir -p '+prefix+' && cd '+prefix+' && sudo timeout -s TERM -k 5 180 '+env+' /tmp/rodinia/'+binary+' '+args
  t=time.time();p=subprocess.run(s['ssh']+[cmd],capture_output=True,text=True,timeout=200);(out/(name+'.log')).write_text(p.stdout+p.stderr);row={'mode':s['mode'],'workload':name,'stage':stage,'label':label,'returncode':p.returncode,'process_wall_seconds':time.time()-t,'utc':t};rows.append(row);save(out/'result.json',rows)
  if p.returncode:raise RuntimeError(str(out)+' '+name+' failed')
  row['sha256']=remote(s,'sha256sum '+prefix+'/full-output.bin').split()[0];row['correct']=row['sha256']==next(x['native_host_sha256'] for x in expected if x['workload']==name);assert row['correct'];row['timing']=json.loads(remote(s,'cat '+prefix+'/timing.json'));
  if stage=='diagnostic':row['diagnostic']=json.loads(remote(s,'cat '+prefix+'/diagnostic.json'))
  save(out/'result.json',rows);print(stage,label,s['mode'],name,row['timing'],flush=True)
 (out/'gpu-after.csv').write_text(subprocess.check_output(gpu_command,text=True))
 return rows

def cleanup_vmw(s):
 assert get('vm',s['name'])['metadata']['uid']==s['vmUID'];k('patch','vm',s['name'],'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Halted"}}');wait(lambda:not get('vmi',s['name']))
 wait(lambda:get('sharedmemorychannel',s['name']).get('status',{}).get('phase')=='Stopped');
 for kind in ['sharedmemorychannel','vm','pvc']:k('delete',kind,s['name'],'-n',NS,'--wait=true','--timeout=90s')
 for kind in ['gpurequest','gpuprofile']:k('delete',kind,s['name'],'-n',NS,'--ignore-not-found','--wait=true','--timeout=90s')
 k('delete','pv',s['name'],'--wait=true','--timeout=90s');ensure_admin();assert s['directory'].startswith('/var/lib/vmweave/bulk-short-20261026/bulk-w-');admin(['rm','-rf',s['directory']]);save(O/'identities'/s['name']/'cleanup.json',{'removed':True})
