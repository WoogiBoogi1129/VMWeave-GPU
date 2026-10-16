"""Scoped GPU 2 VFIO transition, with reversible monitor scheduling changes."""
import json,sys,time
from campaign import c,BASE,s
BDF='0000:aa:00.0';RESOURCE='vmweave.io/ai-perf-passthrough'
def patch(kind,name,ns,obj):return c.k('patch',kind,name,'-n',ns,'--type=merge','-p',json.dumps(obj))
def monitor(paused):
 for name,ns,file in [('hami-device-plugin','kube-system','hami-ds-before.json'),('nvidia-dcgm-exporter','gpu-operator','dcgm-ds-before.json')]:
  selector=json.loads((BASE/file).read_text())['spec']['template']['spec'].get('nodeSelector',{})
  selector['vmweave.io/ai-perf-paused']='true' if paused else None
  patch('ds',name,ns,{'spec':{'template':{'spec':{'nodeSelector':selector}}}})
  if paused:
   uid=c.get('ds',name,ns=ns)['metadata']['uid']
   c.wait(lambda:not any(any(o['uid']==uid for o in p['metadata'].get('ownerReferences',[])) for p in json.loads(c.k('get','pods','-n',ns,'-o','json'))['items']),seconds=90)
  else:c.k('rollout','status','ds/'+name,'-n',ns,'--timeout=120s')
def host(script,*args):return c.k('exec','-i','-n',c.NS,c.HELPER,'--','chroot','/host','python3','-',*args,input=script,timeout=90)
def bind(driver):
 script='''import pathlib,sys,json
bdf,driver=sys.argv[1:];p=pathlib.Path('/sys/bus/pci/devices')/bdf
assert (p/'vendor').read_text().strip()=='0x10de'
assert (p/'device').read_text().strip()=='0x2bb5'
assert [x.name for x in (p/'iommu_group/devices').iterdir()]==[bdf]
old=(p/'driver').resolve().name
if old==driver:print('already bound',driver);raise SystemExit
if driver=='vfio-pci':
 holders=[]
 for proc in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   for fd in (proc/'fd').iterdir():
    try:
     if str(fd.readlink())=='/dev/nvidia2':holders.append(int(proc.name));break
    except OSError:pass
  except OSError:pass
 assert not holders,holders
(p/'driver_override').write_text(driver)
(p/'driver/unbind').write_text(bdf)
pathlib.Path('/sys/bus/pci/drivers',driver,'bind').write_text(bdf)
if driver=='nvidia':(p/'driver_override').write_text('\\n')
print(json.dumps({'bdf':bdf,'before':old,'after':(p/'driver').resolve().name}))
'''
 print(host(script,BDF,driver),flush=True)
def to_native():
 apps=c.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'])
 if s.GPU in apps:raise RuntimeError('Target GPU has compute process')
 c.admin(['chroot','/host','modprobe','vfio-pci'])
 before=json.loads((BASE/'kubevirt-before.json').read_text())['items'][0]
 cfg=before['spec']['configuration'].get('permittedHostDevices',{})
 cfg.setdefault('pciHostDevices',[]).append({'pciVendorSelector':'10DE:2BB5','resourceName':RESOURCE})
 patch('kubevirt',before['metadata']['name'],'kubevirt',{'spec':{'configuration':{'permittedHostDevices':cfg}}})
 monitor(True)
 try:bind('vfio-pci')
 except Exception:
  monitor(False);raise
 c.wait(lambda:json.loads(c.k('get','node','gpu-4','-o','json'))['status'].get('allocatable',{}).get(RESOURCE)=='1',seconds=180)
 monitor(False)
def to_vmweave():
 monitor(True);bind('nvidia');monitor(False)
 before=json.loads((BASE/'kubevirt-before.json').read_text())['items'][0]
 patch('kubevirt',before['metadata']['name'],'kubevirt',{'spec':{'configuration':{'permittedHostDevices':before['spec']['configuration'].get('permittedHostDevices')}}})
 c.call(['nvidia-smi','-i',s.GPU])
if __name__=='__main__':
 {'native':to_native,'vmweave':to_vmweave}[sys.argv[1]]()
