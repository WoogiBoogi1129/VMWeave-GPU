"""Verify registered-pointer rejection from command brackets and complete endpoint traces."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();out=args.run
subprocess.run([sys.executable,str(Path(__file__).with_name('analyze_own_boundary.py')),str(out)],check=True)
result=json.loads((out/'result.json').read_text());joined=json.loads((out/'joined-requests.json').read_text());observations=[]
for attempt in result['cross_results']:
 name=attempt['requester'];r=attempt['observation'];active=None;brackets=[];events=[]
 for line in (out.parent/'runs'/name/'probe-stderr.txt').read_text().splitlines():
  if line.startswith('BOUNDARY_COMMAND '):
   marker=json.loads(line.split(' ',1)[1]);active=marker['sequence'] if marker['stage']=='begin' else None
   if marker['sequence']==r['sequence']:brackets.append(marker)
  elif line.startswith('FLYT_TRACE ') and active==r['sequence']:events.append(json.loads(line.split(' ',1)[1]))
 assert [x['stage'] for x in brackets]==['begin','end']
 assert all(x['op']==r['op'] for x in brackets)
 assert r['target']==attempt['target_buffer']['address']
 assert r['local_lookup']!=0 and r['launch']==1 and r['sync']==-1 and r['copy']==-1 and not r['read_valid']
 assert not any(x['api_id']==0x2033 for x in events)
 matching=[x for x in joined if x['vm']==name and x['command'] and x['command']['sequence']==r['sequence']]
 assert not any(x['api_id']==0x2033 for x in matching)
 observations.append({'requester':name,'target_vm':attempt['target_vm'],'operation':r['op'],'sequence':r['sequence'],'guest_kernel_submits':0,'worker_kernel_receipts':0,'classification':'GUEST_REJECTED_BEFORE_SUBMIT','read_output_valid':False})
assert len(observations)==4
checks=[]
for entry in json.loads((out/'events.json').read_text()):
 checks.extend(r for r in entry['rows'] if r['event']=='check')
assert all(r['code']==0 and r['mismatches']==0 for r in checks)
for name in result['sessions']:
 assert json.loads((out.parent/'runs'/name/'cleanup.json').read_text())['released']
summary={'status':'REGISTERED_PATH_REJECTION_VERIFIED','cross_attempts':observations,'matched_requests':len(joined),
 'positive_control_kernels':sum(x['api_id']==0x2033 for x in joined),'buffer_checks':len(checks),'buffer_mismatches':0,
 'gpu_cross_access_executed':False,'gpu_memory_protection_verdict':'INCONCLUSIVE','cleanup_verified':True}
(out/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
