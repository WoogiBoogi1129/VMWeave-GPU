"""After all measurements: remove only UID-matched campaign service Pods."""
import json,subprocess,time,sys
from pathlib import Path
sys.path.insert(0,'experiments/evidence')
from campaign_runtime import k,get,GPU
b=Path('.local/overhead-20260929');o=Path('experiments/evidence/results/2026-09-29-overhead');details=[]
assert (o/'publication-cutoff.json').exists()
assert not any(p.name.isdigit() and (p/'cmdline').exists() and b'experiments/evidence/run_overhead.py\x00' in (p/'cmdline').read_bytes() for p in Path('/proc').iterdir())
assert json.loads((o/'validation.json').read_text())['status']=='PASS'
for f in ['retention.json','cell-retention.json','patched-retention.json']:
 saved=json.loads((b/f).read_text());name=saved['metadata']['name'];uid=saved['metadata']['uid'];current=get('pod',name)
 if current:
  assert current['metadata']['uid']==uid,(name,'UID changed')
  k(['delete','pod',name,'-n','flyt-evidence','--wait=true','--timeout=90s'])
 details.append({'pod':name,'uid':uid,'removed':get('pod',name) is None})
legacy=json.loads((b/'legacy.json').read_text());name='evidence-perf-manager';current=get('pod',name)
if current:
 assert current['metadata']['uid']==legacy['manager_uid']
 (o/'last-manager.log').write_text(k(['logs','-n','flyt-evidence',name,'-c','manager']))
 k(['delete','pod',name,'-n','flyt-evidence','--wait=true','--timeout=90s'])
details.append({'pod':name,'uid':legacy['manager_uid'],'removed':get('pod',name) is None})
vms=json.loads(k(['get','vmi','-A','-o','json']))['items'];baseline=next(v for v in vms if v['metadata']['namespace']=='flyt-infra-validation' and v['metadata']['name']=='basic-vm');assert baseline['metadata']['uid']=='7d79ad6c-9a38-4242-b7a1-31c5a59f128b' and baseline['status']['phase']=='Running'
active_vms=[v['metadata']['name'] for v in vms if v['metadata']['name'].startswith('evidence-perf-')];assert not active_vms,active_vms
pods=json.loads(k(['get','pods','-A','-o','json']))['items'];active_pods=[p['metadata']['name'] for p in pods if (p['metadata']['name'].startswith('evidence-perf-') or p['metadata']['name'].startswith('virt-launcher-evidence-perf-')) and p.get('status',{}).get('phase') not in ['Succeeded','Failed']];assert not active_pods,active_pods
channels=json.loads(k(['get','flytsharedmemorychannels','-n','flyt-evidence','-o','json']))['items'];ours=[{'name':c['metadata']['name'],'uid':c['metadata']['uid'],'phase':c.get('status',{}).get('phase')} for c in channels if c['metadata']['name'].startswith('evidence-perf-')];assert all(c['phase']=='Released' for c in ours),ours
processes=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],text=True).strip();assert not processes,processes
(o/'resource-cleanup.json').write_text(json.dumps({'utc':time.time(),'removed_pods':details,'channels':ours},indent=2)+'\n')
audit={'status':'PASS','utc':time.time(),'active_experiment_VMs':0,'active_experiment_Pods':0,'owned_channels_all_Released':True,'target_GPU_compute_processes':0,'baseline_VM':'basic-vm','baseline_VM_UID_preserved':True,'baseline_VM_phase':'Running','details':'resource-cleanup.json'}
(o/'final-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
