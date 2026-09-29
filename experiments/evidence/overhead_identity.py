"""Read actual VM specifications without guest/cloud-init secrets or guest work."""
import json,subprocess,time,sys,os
from pathlib import Path
os.sched_setaffinity(0,{48,49,50,51});out=Path(sys.argv[1])
while True:
 for run in out.glob('r*-*'):
  if (run/'vm-specification.json').exists() or not (run/'identity.json').exists():continue
  ident=json.loads((run/'identity.json').read_text());path=ident['path']
  if path=='N':continue
  name='evidence-perf-'+run.name[1:].lower();ns='flyt-overhead-tcp' if path=='T' else 'flyt-evidence'
  result=subprocess.run(['kubectl','get','vmi',name,'-n',ns,'-o','json','--ignore-not-found'],capture_output=True,text=True)
  if not result.stdout.strip():continue
  vm=json.loads(result.stdout)
  assert vm['metadata']['uid']==ident['vmi_uid']
  record={'name':name,'namespace':ns,'vmi_uid':vm['metadata']['uid'],'cpu':vm['spec']['domain']['cpu'],'memory':vm['spec']['domain'].get('memory'),'resources':vm['spec']['domain']['resources'],'guest_images':[v['containerDisk']['image'] for v in vm['spec']['volumes'] if 'containerDisk' in v],'node':vm['status'].get('nodeName'),'interfaces':vm['status'].get('interfaces'),'observed_utc':time.time(),'collection':'read-only Kubernetes API; cloud-init omitted'}
  (run/'vm-specification.json').write_text(json.dumps(record,indent=2)+'\n')
 time.sleep(5)
