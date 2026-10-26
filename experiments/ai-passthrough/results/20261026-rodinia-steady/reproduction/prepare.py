from pathlib import Path
import json,subprocess,time,uuid
R=Path.cwd();B=R/'.local/rodinia-steady-20261026';O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady';NS='rodinia-flyt-1026';NAME='flyt-qualification';ADMIN='rodinia-admin-1026';H='/var/lib/vmweave/rodinia-steady-20261026/flyt';images=json.loads((R/'deploy/releases/v0.5.3.json').read_text())['images']
def k(*a,**kw):return subprocess.check_output(['kubectl',*map(str,a)],text=True,**kw)
def get(kind,name,ns=NS):
 s=k('get',kind,name,'-n',ns,'--ignore-not-found','-o','json');return json.loads(s) if s.strip() else None
def create(o):return json.loads(k('create','-f','-','-o','json',input=json.dumps(o)))
def wait(fn,t=240):
 end=time.monotonic()+t
 while time.monotonic()<end:
  x=fn()
  if x:return x
  time.sleep(2)
 raise TimeoutError('resource wait')
def admin(code):return k('exec','-i','-n',NS,ADMIN,'--','chroot','/host','python3','-',input=code)
assert not get('namespace',NS)
create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':NS,'labels':{'experiment':'rodinia-steady-20261026'}}})
create({'apiVersion':'v1','kind':'Pod','metadata':{'name':ADMIN,'namespace':NS},'spec':{'nodeName':'gpu-4','terminationGracePeriodSeconds':1,'hostPID':True,'restartPolicy':'Never','automountServiceAccountToken':False,'containers':[{'name':'admin','image':images['worker'],'command':['sleep','3600'],'securityContext':{'privileged':True,'runAsUser':0},'volumeMounts':[{'name':'host','mountPath':'/host'}]}],'volumes':[{'name':'host','hostPath':{'path':'/','type':'Directory'}}]}})
wait(lambda:get('pod',ADMIN)['status']['phase']=='Running')
for n in []: # image already imported and pinned
 p=B/(n+'.tar');assert p.exists() and (B/'exports-complete').exists()
 print(admin("import subprocess\nsubprocess.run(['podman','load','-i',%r],check=True)\n"%str(p)),flush=True)
aid=uuid.uuid4().hex;generation=uuid.uuid4().hex;d=H+'/shm';state={'namespace':NS,'name':NAME,'aid':aid,'generation':generation,'directory':H,'shm':d};(B/'state.json').write_text(json.dumps(state,indent=2))
print(admin("import os,json\nfrom pathlib import Path\np=Path(%r);p.mkdir(parents=True,exist_ok=False);p.chmod(0o777)\na=p/%r;a.mkdir();a.chmod(0o777)\nf=a/'channel';f.touch();f.chmod(0o666)\nwith f.open('r+b') as h:h.truncate(2**32)\n(a/'ready.json').write_text(json.dumps(%r))\n"%(d,aid,{'allocationId':aid,'generation':generation,'regionBytes':2**32})),flush=True)
create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':'rodinia-flyt-shm-1026'},'spec':{'capacity':{'storage':'4Gi'},'volumeMode':'Filesystem','accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':NS,'name':'shm'},'local':{'path':d},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':'shm','namespace':NS},'spec':{'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','storageClassName':'','volumeName':'rodinia-flyt-shm-1026','resources':{'requests':{'storage':'4Gi'}}}})
# Stopped VM template. No VMWeave allocation or Worker is attached to this Flyt VM.
hook=[{'args':['--version','v1alpha2'],'image':images['hook'],'pvc':{'name':'shm','sharedComputePath':'/var/run/flyt-channel','volumePath':'/flyt-channel'}}]
key=(R/'.local/thesis-isolation-20261012/artifacts/guest-key.pub').read_text().strip()
vm={'apiVersion':'kubevirt.io/v1','kind':'VirtualMachine','metadata':{'name':NAME,'namespace':NS},'spec':{'runStrategy':'Halted','template':{'metadata':{'annotations':{'hooks.kubevirt.io/hookSidecars':json.dumps(hook),'vmweave.io/shm-allocation':aid,'vmweave.io/shm-generation':generation}},'spec':{'nodeSelector':{'kubernetes.io/hostname':'gpu-4'},'domain':{'cpu':{'cores':8},'resources':{'requests':{'memory':'16Gi'}},'devices':{'disks':[{'name':'root','disk':{'bus':'virtio'}},{'name':'cloudinit','disk':{'bus':'virtio'}}],'interfaces':[{'name':'default','masquerade':{}}]}},'networks':[{'name':'default','pod':{}}],'volumes':[{'name':'root','containerDisk':{'image':'localhost/flyt-evidence-guest@sha256:47e520785c49e6db93631ef4876dcb40b73b23ffc766327e6b02cdfe3496c052'}},{'name':'cloudinit','cloudInitNoCloud':{'userData':'#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+key+'\n'}}]}}}}
created=create(vm);state['vmUID']=created['metadata']['uid'];(B/'state.json').write_text(json.dumps(state,indent=2))
import rodinia_campaign as h
h.arm_affinity('flyt-'+__import__('os').environ['RODINIA_LABEL'],lambda args:k('exec','-n',NS,ADMIN,'--','chroot','/host',*args))
k('delete','pod',ADMIN,'-n',NS,'--wait=true','--timeout=60s')
k('patch','vm',NAME,'-n',NS,'--type=merge','-p','{"spec":{"runStrategy":"Always"}}')
v=wait(lambda: x if (x:=get('vmi',NAME)) and x.get('status',{}).get('phase')=='Running' and (x['status'].get('interfaces') and x['status']['interfaces'][0].get('ipAddress')) else None)
state['ip']=v['status']['interfaces'][0]['ipAddress'];state['vmUID']=get('vm',NAME)['metadata']['uid'];state['vmiUID']=v['metadata']['uid'];(B/'state.json').write_text(json.dumps(state,indent=2));(O/'flyt-vm.json').write_text(json.dumps(v,indent=2));print('Flyt isolated VM running',flush=True)
