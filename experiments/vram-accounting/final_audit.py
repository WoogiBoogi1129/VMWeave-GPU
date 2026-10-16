"""Read-only final resource audit. Does not force any detach or finalizer."""
import json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R=P/'results/20261016';E=P/'evidence/20261016';B=ROOT/'.local/vram-accounting-20261016'
def k(*args):return json.loads(subprocess.check_output(['kubectl',*args,'-o','json'],text=True))
s=json.loads((E/'summary.json').read_text());assert s['final'];names=[x['run'] for x in s['singles']]+[n for x in s['pairs'] for n in x['sessions']]+[x['run'] for x in s['torch']]+[x['run'] for x in s['supplementary_trained_boundary']];assert len(names)==42
inventory={ns:{kind:k('-n',ns,'get',kind)['items'] for kind in ['sharedmemorychannels','pods','vmi']} for ns in ['vmweave-test-a','vmweave-test-b']}
rows=[]
for name in names:
 matches=[(ns,c) for ns,v in inventory.items() for c in v['sharedmemorychannels'] if c['metadata']['name']==name];assert len(matches)==1
 ns,c=matches[0];uid=c['metadata']['uid'];pods=[p for p in inventory[ns]['pods'] if any(x.get('uid')==uid for x in p['metadata'].get('ownerReferences',[]))];vmi=[v for v in inventory[ns]['vmi'] if v['metadata']['name']==name]
 assert c['status']['phase']=='Released' and not vmi and not any(p['metadata']['name'].endswith('-worker') for p in pods)
 rows.append({'name':name,'namespace':ns,'channel_uid':uid,'phase':c['status']['phase'],'vmi_absent':True,'worker_absent':True})
excluded=[]
excluded_names=[d.name for d in (R/'runs').glob('vram-pilot-*')]+['vram-pair-r1-ab-a','vram-pair-r1-ab-b','vram-pair-v2-r1-ab-b','vram-mlp-boundary-r1-1024']
for name in excluded_names:
 matches=[(ns,c) for ns,v in inventory.items() for c in v['sharedmemorychannels'] if c['metadata']['name']==name];assert len(matches)==1
 ns,c=matches[0];assert c['status']['phase']=='Released'
 assert not any(v['metadata']['name']==name for v in inventory[ns]['vmi'])
 assert not any(p['metadata']['name'].endswith('-worker') and any(o.get('uid')==c['metadata']['uid'] for o in p['metadata'].get('ownerReferences',[])) for p in inventory[ns]['pods'])
 excluded.append({'name':name,'namespace':ns,'phase':c['status']['phase'],'channel_uid':c['metadata']['uid'],'excluded_from_formal_measurements':True})
failed=k('-n','vmweave-test-a','get','sharedmemorychannel','vram-pair-v2-r1-ab-a');fp=k('-n','vmweave-test-a','get','pod',failed['status']['resourcePrefix']+'-worker')
before=json.loads((B/'existing-vmi.json').read_text());existing=k('-n','vmweave-test-a','get','vmi','vmweave-k8s-01');assert existing['metadata']['uid']==before['metadata']['uid'] and existing['status']['phase']=='Running'
gpu=subprocess.check_output(['nvidia-smi','-i','GPU-7d708c42-8d4a-16d5-0746-474567157aa3','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip();processes=subprocess.check_output(['nvidia-smi','-i','GPU-7d708c42-8d4a-16d5-0746-474567157aa3','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True).strip();assert int(gpu)<=16 and not processes
result={'audited_utc':time.time(),'measured_runs':rows,'all_42_measured_runs_released':True,'excluded_runs_released':excluded,'gpu_memory_mib':int(gpu),'gpu_processes':processes,'existing_vm':{'name':existing['metadata']['name'],'uid':existing['metadata']['uid'],'same_vmi_uid':True,'phase':existing['status']['phase']},'failed_preparation_unreclaimed':{'name':failed['metadata']['name'],'phase':failed['status']['phase'],'reason':failed['status']['reason'],'worker_pod_uid':fp['metadata']['uid'],'worker_phase':fp['status']['phase'],'worker_node':fp['spec'].get('nodeName'),'container_statuses':fp['status'].get('containerStatuses',[]),'finalizers':fp['metadata'].get('finalizers',[]),'note':'Unscheduled Worker never started; retained Channel/backing and Failed Pod metadata. Not counted as Released. No forced detach/finalizer edits performed.'}}
(E/'final-audit.json').write_text(json.dumps(result,indent=2)+'\n');print('All 42 measured runs released; original VM preserved; GPU empty. One failed preparation remains Draining.')
