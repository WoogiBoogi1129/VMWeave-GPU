"""Read-only final infrastructure and evidence audit after campaign cleanup."""
from common import *
assert (OUT/'followup-complete.json').exists()
node=json.loads(k('get','node','gpu-4','-o','json'))
conditions={r['type']:r['status'] for r in node['status']['conditions']}
assert conditions['Ready']=='True' and all(conditions[x]=='False' for x in ['DiskPressure','MemoryPressure','PIDPressure'])
compute=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'])
assert GPU not in compute
pods=json.loads(k('get','pods','-A','-o','json'))['items']
infra=[p for p in pods if p['metadata']['namespace'] in ['vmweave-system','kubevirt'] and p['status'].get('phase')=='Running']
assert infra and all(all(c.get('ready') for c in p['status'].get('containerStatuses',[])) for p in infra)
deployments=[]
for ns in ['vmweave-system','kubevirt']:
 for d in json.loads(k('get','deployments','-n',ns,'-o','json'))['items']:
  desired=d['spec'].get('replicas',1);ready=d['status'].get('readyReplicas',0);assert ready>=desired
  deployments.append({'namespace':ns,'name':d['metadata']['name'],'desired':desired,'ready':ready})
runs={p.name for p in (OUT/'runs').iterdir() if p.is_dir()}
left=[]
for resource in ['vm','vmi','pvc','pv','gpuprofiles.vmweave.io','gpurequests.vmweave.io','sharedmemorychannels.vmweave.io']:
 for ns in ([NS,'vmweave-performance-tcp'] if resource in ['vm','vmi'] else [NS]):
  for obj in json.loads(k('get',resource,'-n',ns,'-o','json'))['items']:
   name=obj['metadata']['name']
   if name in runs or name.startswith('scprofile-') and name[10:] in runs:left.append({'kind':obj['kind'],'name':name,'namespace':ns})
assert not left,left
owned_pods=[p['metadata']['name'] for p in pods if p['metadata']['namespace'] in [NS,'vmweave-performance-tcp'] and (p['metadata']['name'].startswith('hd-') or p['metadata']['name'].startswith('virt-launcher-hd-'))]
assert not owned_pods,owned_pods
production=call(['git','diff','--name-only','00cf878','--','runtime','operator','deploy','scripts'])
assert not production.strip()
save(OUT/'final-audit.json',{'utc':time.time(),'node_conditions':conditions,'target_gpu_no_compute_process':True,'compute_processes':compute,'deployments':deployments,'infra':[{'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],'phase':p['status']['phase'],'ready':all(c.get('ready') for c in p['status'].get('containerStatuses',[]))} for p in infra],'campaign_resources_remaining':left,'campaign_pods_remaining':owned_pods,'production_runtime_operator_deploy_scripts_unchanged':True})
(OUT/'pods-after.txt').write_text(k('get','pods','-A','-o','wide'))
(OUT/'gpu-after.txt').write_text(call(['nvidia-smi','-q']))
print('PASS: node Ready, no pressure, infrastructure Ready, target GPU idle, campaign resources removed')
