"""Site-specific isolated infrastructure; no credentials are embedded."""
import json, subprocess as S, time, shlex, os, hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2]
B=R/'.local/training-threeway-20261102'
O=R/'experiments/training-threeway/results/20261102'
NS='training-threeway-1102'; GPU='GPU-772181af-05a4-0c24-de59-8487bd37c142'
H='/var/lib/vmweave/training-threeway-20261102'
IMAGES=json.loads((R/'deploy/releases/v0.5.5.json').read_text())['images']
KEY=R/'.local/thesis-isolation-20261012/artifacts/guest-key'
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def k(*a,**kw):return S.check_output(['kubectl',*map(str,a)],text=True,**kw)
def get(kind,name,ns=NS):
 t=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json');return json.loads(t) if t.strip() else None
def create(x):return json.loads(k('create','-f','-','-o','json',input=json.dumps(x)))
def wait(f,seconds=300):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  x=f()
  if x:return x
  time.sleep(2)
 raise TimeoutError('resource wait')
def admin(code,timeout=120):return k('exec','-i','-n',NS,'admin','--','chroot','/host','python3','-',input=code,timeout=timeout)
def patch(kind,name,obj,ns=NS):return k('patch',kind,name,'-n',ns,'--type=merge','-p',json.dumps(obj))
def disk(name,source=None,shm=False,ns=NS):
 path=H+'/'+name
 if get('pvc',name,ns):
  assert get('pv','tt-'+name)['spec']['local']['path']==path
  return path
 code=f"from pathlib import Path\nimport subprocess,os\np=Path({path!r});p.mkdir(parents=True,exist_ok=False)\n"
 if source:code+=f"subprocess.run(['qemu-img','convert','-O','raw',{str(source)!r},str(p/'disk.img')],check=True)\nos.chown(p/'disk.img',107,107)\nos.chmod(p/'disk.img',0o660)\n"
 code+='os.chown(p,107,107)\n';admin(code,180)
 create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':'tt-'+name},'spec':{'capacity':{'storage':'32Gi' if not shm else '4Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':ns,'name':name},'local':{'path':path},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
 create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':ns},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':'tt-'+name,'resources':{'requests':{'storage':'32Gi' if not shm else '4Gi'}}}})
 return path

def template(name,diskname,ns=NS):
 v=json.loads((R/'.local/ai-passthrough-20261016/VirtualMachine-ai-perf-native.json').read_text())
 v['metadata']={'name':name,'namespace':ns,'labels':{'experiment':'training-threeway-20261102'}}
 v['spec']['runStrategy']='Halted';v['spec']['template']['metadata']={}
 t=v['spec']['template']['spec'];t['volumes'][0]['persistentVolumeClaim']['claimName']=diskname
 t['domain']['cpu']['cores']=8;t['domain']['resources']['requests']['memory']='16Gi'
 t['domain']['devices']['interfaces'][0]['macAddress']='02:00:'+':'.join(hashlib.sha256(name.encode()).hexdigest()[i:i+2] for i in range(0,8,2))
 ci=t['volumes'][1]['cloudInitNoCloud'];ci.pop('networkData',None)
 ci['userData']='#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+KEY.with_suffix('.pub').read_text().strip()+'\nssh_pwauth: false\n'
 return v

def start(name,ns=NS):
 patch('vm',name,{'spec':{'runStrategy':'Always'}},ns)
 v=wait(lambda:x if (x:=get('vmi',name,ns)) and x.get('status',{}).get('phase')=='Running' and x['status'].get('interfaces') and x['status']['interfaces'][0].get('ipAddress') else None)
 ip=v['status']['interfaces'][0]['ipAddress']
 opts=['-i',str(KEY),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(B/('known-hosts-'+v['metadata']['uid']))]
 s={'name':name,'namespace':ns,'ip':ip,'vmiUID':v['metadata']['uid'],'ssh':['ssh',*opts,'ubuntu@'+ip],'scp':['scp',*opts]}
 pin(s)
 wait(lambda:S.run(s['ssh']+['true'],capture_output=True,timeout=8).returncode==0)
 save(B/(name+'-ssh.json'),s);save(O/'inventory'/f'{name}-{v["metadata"]["uid"]}.json',v)
 remote(s,'sudo timedatectl set-ntp false')
 return s

def stop(name,ns=NS):
 patch('vm',name,{'spec':{'runStrategy':'Halted'}},ns)
 wait(lambda:not get('vmi',name,ns))
 wait(lambda:not any(x['metadata']['name'].startswith('virt-launcher-'+name+'-') for x in json.loads(k('get','pods','-n',ns,'-o','json'))['items']))

def remote(s,cmd,**kw):return S.check_output(s['ssh']+[cmd],text=True,**kw)
def copy(s,files,target):return S.run(s['scp']+[str(f) for f in files]+['ubuntu@'+s['ip']+':'+target],check=True,capture_output=True)
def pin(s,worker=None):
 pods=json.loads(k('get','pods','-n',s['namespace'],'-o','json'))['items']
 launcher=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+s['name']+'-'))
 targets={launcher['metadata']['uid']:list(range(0,8))}
 if worker:targets[next(p['metadata']['uid'] for p in pods if p['metadata']['name']==worker)]=list(range(8,12))
 code='''import pathlib,os,json
out=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text()
  for uid,cpus in TARGETS.items():
   if uid in cg or uid.replace('-','_') in cg:
    for t in (p/'task').iterdir():os.sched_setaffinity(int(t.name),cpus)
    out.append({'pid':int(p.name),'comm':(p/'comm').read_text().strip(),'cpus':cpus,'uid':uid})
 except (OSError,ProcessLookupError):pass
assert out
print(json.dumps(out))
'''.replace('TARGETS',repr(targets))
 result=json.loads(admin(code));save(O/'inventory'/(s['name']+'-affinity-'+str(time.time_ns())+'.json'),result)
 return result

if __name__=='__main__':
 import sys
 if sys.argv[1]=='base':
  disk('base',R/'.local/pytorch-path-20260922/guest-disk/disk.qcow2')
  create(template('base','base'));s=start('base');pin(s)
  remote(s,'sudo mkdir -p /opt/flyt-evidence/driver; sudo chown -R ubuntu:ubuntu /opt/flyt-evidence; mkdir -p /tmp/training')
  copy(s,[R/'.local/pytorch-path-20260922'/f for f in ['driver-source.tgz','firmware.tgz']],'/opt/flyt-evidence/')
  copy(s,[f for f in (R/'.local/pytorch-path-20260922/driver').iterdir() if f.is_file()],'/opt/flyt-evidence/driver/')
  with (R/'.local/thesis-isolation-20261012/guest-python-cuda.tgz').open('rb') as f:S.run(s['ssh']+['sudo tar -xz -C / opt/torch-venv opt/flyt-cuda-libs'],stdin=f,check=True)
  remote(s,'sudo apt-get update -o Acquire::GzipIndexes=true && sudo apt-get install -y --no-install-recommends gcc make libelf-dev linux-headers-$(uname -r)',timeout=600)
  remote(s,'cd /opt/flyt-evidence && tar -xzf driver-source.tgz && cd nvidia-580.173.02 && make -j8 modules',timeout=600)
  remote(s,'sudo mkdir -p /lib/modules/$(uname -r)/updates/flyt; sudo cp /opt/flyt-evidence/nvidia-580.173.02/*.ko /lib/modules/$(uname -r)/updates/flyt/; sudo depmod -a; sudo mkdir -p /lib/firmware; sudo tar -xzf /opt/flyt-evidence/firmware.tgz -C /lib/firmware')
  copy(s,[R/'experiments/training-threeway/bench.py'],'/tmp/training/')
  remote(s,'sudo sync');stop('base');print('BASE_READY',flush=True)
