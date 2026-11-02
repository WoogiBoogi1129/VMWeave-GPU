"""Prepare three stopped VMs from a single frozen OS disk."""
from lab import *
import uuid
assert not get('vmi','base')
for mode in ['passthrough','flyt','vmweave']:
 ns='vmweave-test-a' if mode=='vmweave' else NS
 name='tt-'+mode+'-1102'
 if get('vm',name,ns):continue
 disk(name,H+'/base/disk.img',ns=ns)
 v=template(name,name,ns)
 if mode=='passthrough':
  v['spec']['template']['spec']['domain']['devices']['gpus']=[{'deviceName':'vmweave.io/training-passthrough','name':'gpu'}]
 elif mode=='flyt':
  path=disk('flyt-shm',shm=True)
  existing=json.loads(admin(f"import json;from pathlib import Path;print(json.dumps([p.name for p in Path({path!r}).iterdir() if p.is_dir()]))"))
  aid=existing[0] if existing else uuid.uuid4().hex;generation=uuid.uuid4().hex
  admin(f"from pathlib import Path\nimport os,json\np=Path({path!r})/{aid!r};p.mkdir(exist_ok=True);p.chmod(0o777)\nf=p/'channel';f.touch();f.chmod(0o666)\nwith f.open('r+b') as h:h.truncate(2**32)\n(p/'ready.json').write_text(json.dumps({dict(allocationId=aid,generation=generation,regionBytes=2**32)!r}))")
  hooks=[{'args':['--version','v1alpha2'],'image':IMAGES['hook'],'pvc':{'name':'flyt-shm','sharedComputePath':'/var/run/flyt-channel','volumePath':'/flyt-channel'}}]
  v['spec']['template']['metadata']={'annotations':{'hooks.kubevirt.io/hookSidecars':json.dumps(hooks),'vmweave.io/shm-allocation':aid,'vmweave.io/shm-generation':generation}}
  save(B/'flyt-state.json',{'namespace':NS,'name':name,'aid':aid,'generation':generation,'directory':path,'shm':path})
 create(v)
 if mode=='vmweave':
  disk('tt-vmweave-shm-1102',shm=True,ns=ns)
  create({'apiVersion':'vmweave.io/v1alpha1','kind':'GPUProfile','metadata':{'name':name,'namespace':ns},'spec':{'approved':True,'nodeName':'gpu-4','gpuUUID':GPU,'cores':100,'memoryMiB':8192,'maxClients':1,'hamiNamespace':'kube-system','schedulerName':'hami-scheduler','runtimeClass':'nvidia','workerImage':IMAGES['worker']}})
  S.run(['python3',str(R/'scripts/operator/create-channel.py'),'--lifecycle','VM','--namespace',ns,'--vm',name,'--profile',name,'--pvc','tt-vmweave-shm-1102','--name',name,'--compute','100','--memory','8192Mi','--helper-image',IMAGES['helper'],'--hook-image',IMAGES['hook']],check=True)
  wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped')
  # Install on the first fresh binding before any application owns a session.
  s=start(name,ns);pin(s)
  S.run(s['scp']+['-r',str(R/'.local/v055-release-20261027/published-guest'),'ubuntu@'+s['ip']+':/tmp/package'],check=True)
  remote(s,'sudo sh /tmp/package/install_guest_broker.sh /tmp/package')
  remote(s,'sudo tee /etc/vmweave/guest-broker.env >/dev/null',input='VMWEAVE_BULK_COPY=1\nVMWEAVE_BROKER_REUSE=1\nVMWEAVE_BROKER_GATHER=1\nVMWEAVE_BROKER_OWNER=1\n')
  # No broker has run in this VM yet; reboot with the installed package/config.
  stop(name,ns);wait(lambda:get('sharedmemorychannel',name,ns).get('status',{}).get('phase')=='Stopped')
print('THREE_STOPPED_VMS_READY',flush=True)
