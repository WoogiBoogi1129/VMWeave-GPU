"""Read-only continuity samples for the pre-existing GPU services."""
import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=ROOT/'.local/ai-passthrough-20261016';E=ROOT/'experiments/ai-passthrough/results/20261016'
(B/'service-monitor.pid').write_text(str(os.getpid()))
original=json.loads((B/'pods-before.json').read_text())['items'];names={p['metadata']['name'] for p in original if p['metadata']['namespace']=='aap-serving' and any('nvidia.com/gpu' in c.get('resources',{}).get('limits',{}) for c in p['spec']['containers'])}
prefixes={name.rsplit('-',1)[0]+'-' for name in names}
with (E/'service-continuity.jsonl').open('a') as out:
 while True:
  try:
   ps=json.loads(subprocess.check_output(['kubectl','get','pods','-n','aap-serving','-o','json'],timeout=10))['items']
   rows=[{'name':p['metadata']['name'],'uid':p['metadata']['uid'],'phase':p['status'].get('phase'),'ready':next((q['status'] for q in p['status'].get('conditions',[]) if q['type']=='Ready'),None),'restarts':sum(q.get('restartCount',0) for q in p['status'].get('containerStatuses',[]))} for p in ps if any(p['metadata']['name'].startswith(prefix) for prefix in prefixes)]
   record={'utc':time.time(),'gpu2_driver':Path('/sys/bus/pci/devices/0000:aa:00.0/driver').resolve().name,'services':rows,'missing_original_names':sorted(names-{p['metadata']['name'] for p in ps}),'original_gpu3_pids_alive':{str(pid):Path('/proc',str(pid)).exists() for pid in [1840504,1930105,2359792,2469212]}}
  except Exception as e:record={'utc':time.time(),'error':repr(e)}
  out.write(json.dumps(record)+'\n');out.flush();time.sleep(30)
