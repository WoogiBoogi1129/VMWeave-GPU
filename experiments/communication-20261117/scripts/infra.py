from common import *
KEY=B/'guest-key'
def make_key():
 if not KEY.exists():call(['ssh-keygen','-t','ed25519','-N','','-f',KEY])
def claim(name,ns=NS):
 return create({'apiVersion':'resource.k8s.io/v1','kind':'ResourceClaim','metadata':{'name':name,'namespace':ns},'spec':{'devices':{'requests':[{'name':'gpu','exactly':{'deviceClassName':'vmweave-hami-dra','allocationMode':'ExactCount','count':1,'selectors':[{'cel':{'expression':f'device.attributes["hami-core-gpu.project-hami.io"].uuid == "{GPU}"'}}],'capacity':{'requests':{'memory':'97887Mi','cores':'100'}}}}]}}})
def gpu_pod(name,image,command,env=None,mounts=None,volumes=None):
 claim(name)
 c={'name':'main','image':image,'command':command,'resources':{'claims':[{'name':'gpu'}],'requests':{'cpu':'1','memory':'1Gi'},'limits':{'cpu':'4','memory':'16Gi'}},'env':[{'name':k,'value':v} for k,v in (env or {}).items()],'volumeMounts':[{'name':'work','mountPath':'/work'},*(mounts or [])]}
 p={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NS},'spec':{'nodeSelector':{'kubernetes.io/hostname':NODE},'runtimeClassName':'nvidia','schedulerName':'default-scheduler','restartPolicy':'Never','terminationGracePeriodSeconds':10,'automountServiceAccountToken':False,'resourceClaims':[{'name':'gpu','resourceClaimName':name}],'containers':[c],'volumes':[{'name':'work','hostPath':{'path':str(B/'artifacts'),'type':'Directory'}},*(volumes or [])]}}
 x=create(p);save(O/'manifests'/(name+'.json'),p)
 wait(lambda:get('pod',name).get('status',{}).get('phase')=='Running',300)
 return get('pod',name)
def delete_gpu(name):
 remove('pod',name);remove('resourceclaim',name)
def pin(uid,cpus):
 code='''import os,pathlib,json
out=[]
for p in pathlib.Path('/proc').glob('[0-9]*'):
 try:
  cg=(p/'cgroup').read_text()
  if UID in cg or UID.replace('-','_') in cg:
   for t in (p/'task').iterdir():os.sched_setaffinity(int(t.name),CPUS)
   out.append({'pid':int(p.name),'comm':(p/'comm').read_text().strip(),'cpus':sorted(os.sched_getaffinity(int(p.name)))})
 except (OSError,ProcessLookupError):pass
assert out
print(json.dumps(out))
'''.replace('UID',repr(uid)).replace('CPUS',repr(cpus))
 return json.loads(admin(code))
def disk(name,ns,source=None):
 path=H+'/'+name
 if get('pvc',name,ns):return path
 code=f"from pathlib import Path\nimport os,subprocess\np=Path({path!r});p.mkdir(parents=True,exist_ok=False)\n"
 if source:code+=f"subprocess.run(['qemu-img','convert','-O','raw',{str(source)!r},str(p/'disk.img')],check=True)\nsubprocess.run(['qemu-img','resize','-f','raw',str(p/'disk.img'),'32G'],check=True)\nos.chown(p/'disk.img',107,107);os.chmod(p/'disk.img',0o660)\n"
 code+="os.chown(p,107,107);os.chmod(p,0o770)\n";admin(code,300)
 create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':'32Gi' if source else '4Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':ns,'name':name},'local':{'path':path},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':[NODE]}]}]}}}})
 create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':ns},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':name,'resources':{'requests':{'storage':'32Gi' if source else '4Gi'}}}})
 return path

def make_vm(name,ns,source):
 if get('vm',name,ns):return
 make_key();disk(name,ns,source)
 user='#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+KEY.with_suffix('.pub').read_text().strip()+'\nssh_pwauth: false\n'
 v={'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':name,'namespace':ns},'spec':{'runStrategy':'Halted','template':{'metadata':{'labels':LABEL},'spec':{'nodeSelector':{'kubernetes.io/hostname':NODE},'domain':{'cpu':{'cores':4},'resources':{'requests':{'memory':'16Gi'}},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{},'macAddress':'02:00:'+':'.join(hashlib.sha256(name.encode()).hexdigest()[i:i+2] for i in range(0,8,2))}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','persistentVolumeClaim':{'claimName':name}},{'name':'cloudinit','cloudInitNoCloud':{'userData':user}}]}}}}
 create(v)
def vm_start(name,ns):
 patch('vm',name,{'spec':{'runStrategy':'Always'}},ns)
 v=wait(lambda:x if (x:=get('vmi',name,ns)) and x.get('status',{}).get('phase')=='Running' and x['status'].get('interfaces') and x['status']['interfaces'][0].get('ipAddress') else None,300)
 ip=v['status']['interfaces'][0]['ipAddress'];opts=['-i',str(KEY),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(B/'known-hosts')]
 s={'name':name,'namespace':ns,'ip':ip,'vmi_uid':v['metadata']['uid'],'ssh':['ssh',*opts,'ubuntu@'+ip],'scp':['scp',*opts]}
 wait(lambda:S.run(s['ssh']+['true'],capture_output=True,timeout=8).returncode==0,300)
 pods=json.loads(k('get','pods','-n',ns,'-o','json'))['items'];p=next(p for p in pods if p['metadata']['name'].startswith('virt-launcher-'+name+'-'))
 s.update(launcher=p['metadata']['name'],launcher_uid=p['metadata']['uid']);s['pinning']=pin(s['launcher_uid'],list(range(8,12)))
 save(B/(name+'-connection.json'),s);return s

def remote(s,cmd,**kw):return call(s['ssh']+[cmd],**kw)
def copy(s,paths,target):return call(s['scp']+list(map(str,paths))+['ubuntu@'+s['ip']+':'+target])
def vm_stop(name,ns):
 if not get('vm',name,ns):return
 patch('vm',name,{'spec':{'runStrategy':'Halted'}},ns)
 wait(lambda:not get('vmi',name,ns),180)
 if ns==VNS and get('sharedmemorychannel',name,ns):wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped',180)
