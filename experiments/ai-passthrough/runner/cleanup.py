"""Final guarded cleanup of this campaign's resources, after evidence collection."""
import json,time
from pathlib import Path
from campaign import c,BASE,OUT,ROOT,s
assert json.loads((OUT/'validation.json').read_text())['formal_measurements']==80
assert json.loads((OUT/'equal-budget/validation.json').read_text())['formal_measurements']==12
assert all((OUT/'equal-budget'/f'b{i}-{mode}'/'complete.json').is_file() for i in range(1,4) for mode in ['vmweave','passthrough'])
def obj(kind,name,ns):return c.get(kind,name,ns=ns)
assert Path('/sys/bus/pci/devices/0000:aa:00.0/driver').resolve().name=='nvidia'
apps=c.call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']);assert s.GPU not in apps
(OUT/'gpu-processes-after.csv').write_text(apps)
checks={}
for name,ns,file in [('hami-device-plugin','kube-system','hami-ds-before.json'),('nvidia-dcgm-exporter','gpu-operator','dcgm-ds-before.json')]:
 before=json.loads((BASE/file).read_text());after=obj('ds',name,ns)
 assert before['spec']['template']['spec'].get('nodeSelector',{})==after['spec']['template']['spec'].get('nodeSelector',{})
 assert after['status']['numberReady']==after['status']['desiredNumberScheduled']==1
 checks[name]={'nodeSelector':after['spec']['template']['spec']['nodeSelector'],'ready':True}
before=json.loads((BASE/'kubevirt-before.json').read_text())['items'][0];after=obj('kubevirt',before['metadata']['name'],'kubevirt')
assert before['spec']['configuration'].get('permittedHostDevices')==after['spec']['configuration'].get('permittedHostDevices')
checks['permittedHostDevices_restored']=True
pods=json.loads(c.k('get','pods','-A','-o','json'))['items'];old=json.loads((BASE/'pods-before.json').read_text())['items'];current={p['metadata']['uid']:p for p in pods};services=[]
change=json.loads((OUT/'service-change/observation.json').read_text())
for p in old:
 if (p['metadata']['namespace']=='aap-serving' and any('nvidia.com/gpu' in x.get('resources',{}).get('limits',{}) for x in p['spec']['containers'])) or p['metadata']['name'].startswith('virt-launcher-vmweave-k8s-01-'):
  replaced=p['metadata']['uid'] not in current
  if replaced:
   assert p['metadata']['name']==change['old_pod']
   matches=[q for q in pods if q['metadata']['namespace']=='aap-serving' and q['metadata']['name']==change['new_pod']];assert len(matches)==1
   now=matches[0]
  else:now=current[p['metadata']['uid']]
  assert any(x['type']=='Ready' and x['status']=='True' for x in now['status']['conditions'])
  assert sum(x.get('restartCount',0) for x in now['status']['containerStatuses'])==sum(x.get('restartCount',0) for x in p['status']['containerStatuses'])
  services.append({'namespace':now['metadata']['namespace'],'name':now['metadata']['name'],'uid':now['metadata']['uid'],'ready':True,'original_pod_preserved':not replaced,'container_restarts_unchanged':True})
assert all(Path('/proc',str(pid)).exists() for pid in [1840504,2359792,2469212,change['new_gpu3_pid']])
for ns in ['vmweave-test-a','ai-perf-baseline']:
 assert not any(x['metadata']['name'].startswith('ai-perf-') for x in json.loads(c.k('get','vmi','-n',ns,'-o','json'))['items'])
 assert not any(x['metadata']['name'].endswith('-worker') and x['metadata']['name'].startswith('ai-perf-') for x in pods if x['metadata']['namespace']==ns)
for kind in ['vm','pvc']:
 rows=json.loads(c.k('get',kind,'-n','ai-perf-baseline','-o','json'))['items'];assert all(x['metadata']['name']=='ai-perf-native' for x in rows)
 c.k('delete',kind,'ai-perf-native','-n','ai-perf-baseline','--ignore-not-found','--wait=true','--timeout=90s')
pv=obj('pv','ai-perf-native','default')
if pv:
 assert pv['spec']['local']['path']=='/var/lib/vmweave/ai-perf-20261016/native'
 c.k('delete','pv','ai-perf-native','--wait=true','--timeout=90s')
c.admin(['chroot','/host','python3','-c',"from pathlib import Path;import shutil;p=Path('/var/lib/vmweave/ai-perf-20261016/native');assert p.resolve()==p;shutil.rmtree(p) if p.exists() else None"])
requests=json.loads(c.k('get','gpurequests.vmweave.io','-n','vmweave-test-a','-o','json'))['items']
orphans=[q for q in requests if q['spec'].get('profileRef',{}).get('name') in ['ai-perf-core100-1016','ai-perf-vm-core100-1016']]
if orphans:c.save(OUT/'orphan-requests-before-cleanup.json',orphans)
for q in orphans:
 name=q['metadata']['name'];vm=q['spec']['vmRef']['name'];assert name.startswith('ai-perf-') and vm==name
 assert obj('vm',vm,'vmweave-test-a') is None and obj('vmi',vm,'vmweave-test-a') is None
 assert not any(p['metadata']['name'].startswith(name+'-') for p in pods)
 c.k('delete','gpurequest',name,'-n','vmweave-test-a','--wait=true','--timeout=90s')
for name in ['ai-perf-core100-1016','ai-perf-vm-core100-1016']:
 requests=json.loads(c.k('get','gpurequests.vmweave.io','-n','vmweave-test-a','-o','json'))['items'];assert not any(q['spec'].get('profileRef',{}).get('name')==name for q in requests)
 c.k('delete','gpuprofile',name,'-n','vmweave-test-a','--ignore-not-found')
for kind in ['pods','vms','vmis','persistentvolumeclaims','services','deployments','daemonsets','statefulsets','jobs','cronjobs']:
 assert not json.loads(c.k('get',kind,'-n','ai-perf-baseline','-o','json'))['items'],kind
c.k('delete','namespace','ai-perf-baseline','--wait=true','--timeout=90s')
c.k('delete','pod',c.HELPER,'-n',c.NS,'--wait=true','--timeout=90s')
assert obj('pod',c.HELPER,c.NS) is None
c.save(OUT/'cleanup.json',{'status':'PASS','scope':'Experiment resource cleanup and current readiness; not uninterrupted service continuity','completed_utc':time.time(),'gpu2_driver':'nvidia','gpu2_compute_processes':0,'restored':checks,'existing_services':services,'original_gpu3_pids_alive':{str(pid):Path('/proc',str(pid)).exists() for pid in [1840504,1930105,2359792,2469212]},'service_replacement_observed':change,'native_vm_pvc_pv_namespace_removed':True,'experiment_profiles_removed':True,'helper_removed':True})
print('CAMPAIGN RESOURCE CLEANUP PASS')
