import json,subprocess,pathlib
R=pathlib.Path.cwd(); D=R/'.local/ai-passthrough-20261016'; ns='ai-perf-baseline'; name='ai-perf-native'
def k(*a):return subprocess.check_output(['kubectl',*a],text=True)
def create(x):
 p=D/(x['kind']+'-'+x['metadata']['name']+'.json');p.write_text(json.dumps(x,indent=2));k('create','-f',str(p))
create({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}})
path='/var/lib/vmweave/ai-perf-20261016/native'
script='import pathlib,subprocess,os\np=pathlib.Path('+repr(path)+');p.mkdir(parents=True,exist_ok=False)\nsubprocess.run(["qemu-img","convert","-O","raw",'+repr(str(R/'.local/pytorch-path-20260922/guest-disk/disk.qcow2'))+',str(p/"disk.img")],check=True)\nos.chown(p/"disk.img",107,107)\nos.chmod(p/"disk.img",0o660)\n'
subprocess.run(['kubectl','exec','-i','-n','vmweave-test-a','ai-perf-admin-1016','--','chroot','/host','python3','-'],input=script,text=True,check=True)
create({'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':'16Gi'},'accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','local':{'path':path},'claimRef':{'namespace':ns,'name':name},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':['gpu-4']}]}]}}}})
create({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':ns},'spec':{'storageClassName':'','volumeName':name,'accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'16Gi'}}}})
v=json.load(open('.local/pytorch-path-20260922/evidence-passthrough-v2.json'));v['metadata']={'name':name,'namespace':ns};s=v['spec']['template']['spec'];s['domain']['devices'].pop('gpus');s['domain']['firmware'].pop('uuid');s['domain']['firmware'].pop('serial');s['volumes'][0]['persistentVolumeClaim']['claimName']=name
key=(R/'.local/thesis-isolation-20261012/artifacts/guest-key.pub').read_text().strip();s['volumes'][1]['cloudInitNoCloud']['userData']='#cloud-config\nusers:\n  - name: ubuntu\n    sudo: ALL=(ALL) NOPASSWD:ALL\n    shell: /bin/bash\n    ssh_authorized_keys:\n      - '+key+'\nssh_pwauth: false\n'
create(v)
