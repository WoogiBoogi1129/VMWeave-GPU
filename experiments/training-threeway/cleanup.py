"""Remove only this experiment's resources and restore its scoped configuration changes."""
from backends import *

def cleanup():
 for mode in ['passthrough','flyt','vmweave']:
  name='tt-'+mode+'-1102';ns=VMNS if mode=='vmweave' else NS
  if get('vmi',name,ns):stop(name,ns)
 if get('pod','flyt-server'):k('delete','pod','flyt-server','-n',NS,'--wait=true','--timeout=90s')
 if Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='vfio-pci':transition.transition('nvidia')
 if get('sharedmemorychannel','tt-vmweave-1102',VMNS):
  wait(lambda:get('sharedmemorychannel','tt-vmweave-1102',VMNS).get('status',{}).get('phase')=='Stopped')
  k('delete','sharedmemorychannel','tt-vmweave-1102','-n',VMNS,'--wait=true','--timeout=120s')
 for kind in ['vm','gpurequest','gpuprofile']:
  k('delete',kind,'tt-vmweave-1102','-n',VMNS,'--ignore-not-found','--wait=true','--timeout=90s')
 for name in ['base','tt-passthrough-1102','tt-flyt-1102']:
  k('delete','vm',name,'-n',NS,'--ignore-not-found','--wait=true','--timeout=90s')
 for name,ns in [('base',NS),('tt-passthrough-1102',NS),('tt-flyt-1102',NS),('flyt-shm',NS),('tt-vmweave-1102',VMNS),('tt-vmweave-shm-1102',VMNS)]:
  k('delete','pvc',name,'-n',ns,'--ignore-not-found','--wait=true','--timeout=90s')
  k('delete','pv','tt-'+name,'--ignore-not-found','--wait=true','--timeout=90s')
 # Restore the exact original ConfigMap data if no independent change occurred.
 before=json.loads((B/'hami-config-before.json').read_text());original=json.loads(before['data']['config.json'])
 expected=json.loads(before['data']['config.json']);next(x for x in expected['nodeconfig'] if x['name']=='gpu-4')['filterdevices']['uuid'].remove(GPU)
 current=get('cm','hami-device-plugin','kube-system');now=json.loads(current['data']['config.json'])
 assert now in [expected,original], 'Independent HAMi configuration change: do not overwrite'
 patch('cm','hami-device-plugin',{'data':{'config.json':before['data']['config.json']}},'kube-system')
 k('rollout','restart','ds/hami-device-plugin','-n','kube-system');k('rollout','status','ds/hami-device-plugin','-n','kube-system','--timeout=120s')
 # Preserve unrelated KubeVirt configuration; remove only the test resource entry.
 kv=json.loads(k('get','kubevirt','-n','kubevirt','-o','json'))['items'][0]
 cfg=kv['spec']['configuration'].get('permittedHostDevices') or {}
 cfg['pciHostDevices']=[d for d in cfg.get('pciHostDevices',[]) if d.get('resourceName')!=transition.RESOURCE]
 beforekv=json.loads((B/'kubevirt-before.json').read_text())
 if not any(cfg.values()) and not beforekv['spec']['configuration'].get('permittedHostDevices'):cfg=None
 patch('kubevirt',kv['metadata']['name'],{'spec':{'configuration':{'permittedHostDevices':cfg}}},'kubevirt')
 preserved=[]
 for row in json.loads((O/'inventory/preserved-before.json').read_text()):
  x=get(row['kind'],row['name'],row['namespace'])
  record={'kind':row['kind'],'namespace':row['namespace'],'name':row['name'],'uid_unchanged':x['metadata']['uid']==row['uid'],'spec_unchanged':hashlib.sha256(json.dumps(x['spec'],sort_keys=True).encode()).hexdigest()==row['spec_sha256'],'phase':x.get('status',{}).get('phase')}
  if row['kind']=='vm':
   vmi=get('vmi',row['name'],row['namespace'])
   record['vmi_phase']=vmi.get('status',{}).get('phase') if vmi else None
   record['vmi_ready']=bool(vmi and any(c['type']=='Ready' and c['status']=='True' for c in vmi.get('status',{}).get('conditions',[])))
   assert record['vmi_phase']=='Running' and record['vmi_ready']
  else:assert record['phase']=='Ready'
  preserved.append(record)
  assert record['uid_unchanged'] and record['spec_unchanged']
 idle()
 assert Path('/sys/bus/pci/devices/0000:40:00.0/driver').resolve().name=='nvidia'
 assert get('cm','hami-device-plugin','kube-system')['data']['config.json']==before['data']['config.json']
 (O/'inventory/gpus-after.csv').write_text(S.check_output(['nvidia-smi','--query-gpu=index,uuid,name,driver_version,memory.used,utilization.gpu','--format=csv'],text=True))
 monitors=[]
 for name,ns in transition.MONITORS:
  x=get('ds',name,ns);old=json.loads((B/(name+'-before.json')).read_text())
  assert x['spec']['template']['spec']==old['spec']['template']['spec']
  monitors.append({'namespace':ns,'name':name,'pod_spec_restored':True})
 admin(f"import shutil;from pathlib import Path\np=Path({H!r});assert str(p)=='/var/lib/vmweave/training-threeway-20261102';shutil.rmtree(p)")
 k('delete','namespace',NS,'--wait=true','--timeout=120s')
 (B/'observer.stop').touch()
 (B/'active.json').unlink(missing_ok=True)
 save(O/'cleanup.json',{'utc':time.time(),'test_resources_removed':True,'gpu0_driver':'nvidia','gpu0_compute_idle':True,'hami_config_exactly_restored':True,'monitors':monitors,'preserved':preserved,'scope':'Configuration/current readiness checks, not proof of uninterrupted application-level SLA'})
 print('CLEANUP_COMPLETE',flush=True)
if __name__=='__main__':cleanup()
