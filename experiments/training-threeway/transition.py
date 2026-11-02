"""Restoreable GPU0-only VFIO binding, preserving other GPU applications."""
from lab import *
BDF='0000:40:00.0'; RESOURCE='vmweave.io/training-passthrough'
MONITORS=[('hami-device-plugin','kube-system'),('nvidia-dcgm-exporter','gpu-operator')]
KEYSEL='vmweave.io/training-transition-paused'
def monitors(paused):
 for name,ns in MONITORS:
  old=get('ds',name,ns)
  if not (B/(name+'-before.json')).exists():save(B/(name+'-before.json'),old)
  orig=json.loads((B/(name+'-before.json')).read_text())['spec']['template']['spec'].get('nodeSelector',{})
  assert KEYSEL not in orig
  patch('ds',name,{'spec':{'template':{'spec':{'nodeSelector':{KEYSEL:'true' if paused else None}}}}},ns)
  if paused:
   uid=old['metadata']['uid']
   wait(lambda:not any(any(r['uid']==uid for r in x['metadata'].get('ownerReferences',[])) for x in json.loads(k('get','pods','-n',ns,'-o','json'))['items']),120)
  else:k('rollout','status','ds/'+name,'-n',ns,'--timeout=120s')
def bind(driver):
 assert not get('vmi','tt-passthrough-1102')
 if driver=='vfio-pci':
  assert not S.check_output(['nvidia-smi','-i',GPU,'--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
 code='''from pathlib import Path
import os,json,subprocess
p=Path('/sys/bus/pci/devices/0000:40:00.0')
assert (p/'vendor').read_text().strip()=='0x10de'
assert (p/'device').read_text().strip()=='0x2bb5'
assert [x.name for x in (p/'iommu_group/devices').iterdir()]==['0000:40:00.0']
old=(p/'driver').resolve().name
if old==DRIVER:print('already bound');raise SystemExit
if DRIVER=='vfio-pci':
 holders=[]
 for proc in Path('/proc').glob('[0-9]*'):
  try:
   if '/dev/nvidia0' in [str(x.readlink()) for x in (proc/'fd').iterdir()]:holders.append(int(proc.name))
  except OSError:pass
 assert not holders,holders
 subprocess.run(['modprobe','vfio-pci'],check=True)
(p/'driver_override').write_text(DRIVER)
(p/'driver/unbind').write_text('0000:40:00.0')
Path('/sys/bus/pci/drivers',DRIVER,'bind').write_text('0000:40:00.0')
if DRIVER=='nvidia':(p/'driver_override').write_text('\\n')
print(json.dumps({'before':old,'after':(p/'driver').resolve().name}))
'''.replace('DRIVER',repr(driver))
 print(admin(code,120),flush=True)

def transition(driver):
 kv=json.loads(k('get','kubevirt','-n','kubevirt','-o','json'))['items'][0]
 if not (B/'kubevirt-before.json').exists():save(B/'kubevirt-before.json',kv)
 cfg=kv['spec']['configuration'].get('permittedHostDevices') or {}
 devs=[d for d in cfg.get('pciHostDevices',[]) if d.get('resourceName')!=RESOURCE]
 if driver=='vfio-pci':devs.append({'pciVendorSelector':'10DE:2BB5','resourceName':RESOURCE})
 cfg['pciHostDevices']=devs
 before=json.loads((B/'kubevirt-before.json').read_text())
 if driver=='nvidia' and not any(cfg.values()) and not before['spec']['configuration'].get('permittedHostDevices'):cfg=None
 patch('kubevirt',kv['metadata']['name'],{'spec':{'configuration':{'permittedHostDevices':cfg}}},'kubevirt')
 try:
  monitors(True);bind(driver)
 finally:monitors(False)
 if driver=='vfio-pci':wait(lambda:json.loads(k('get','node','gpu-4','-o','json'))['status'].get('allocatable',{}).get(RESOURCE)=='1',180)
 save(O/'inventory'/('binding-'+str(time.time_ns())+'.json'),{'driver':driver,'bdf':BDF,'utc':time.time()})
if __name__=='__main__':
 import sys
 transition(sys.argv[1])
