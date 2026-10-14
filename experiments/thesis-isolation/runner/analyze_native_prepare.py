"""Independent consistency checks for native preparation; no GPU execution."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);out=p.parse_args().run
result=json.loads((out/'result.json').read_text());ownership=json.loads((out/'ownership.json').read_text());counts={'kernel_operations':0,'buffer_checks':0,'mapping_queries':0}
assert len({x['host']['host_pid'] for x in ownership})==2
assert len({x['ready']['gpu'] for x in ownership})==1
assert all(x['ready']['quota_visible_bytes']==2048*1024*1024 for x in ownership)
for owner in ownership:
 d=out.parent/'runs'/owner['process'];rows=[json.loads(x) for x in (d/'requests-events.jsonl').read_text().splitlines()]
 assert rows[0]['event']=='ready' and rows[0]['address']==owner['ready']['address']
 launches={};operations=[]
 for r in rows:
  if r['event']=='launch_begin':
   assert r['sequence'] not in launches and r['own_buffer'] and r['context_query']==0
   assert r['context']==owner['ready']['context'] and r['target']==owner['ready']['address'];launches[r['sequence']]=r
  elif r['event']=='access':
   assert r['sequence'] in launches and all(r[k]==0 for k in ['prep','launch','sync','copy'])
   assert r['expected']==r['observed'];operations.append(r['op']);counts['kernel_operations']+=1
  elif r['event']=='check':
   assert r['code']==0 and r['mismatches']==0;counts['buffer_checks']+=1
  elif r['event']=='mapping':
   assert not r['gpu_access_issued'];counts['mapping_queries']+=1
 assert operations==['read','write','read'] and len(launches)==3
 assert json.loads((d/'cleanup.json').read_text())['released']
for query in result['mapping_queries']:
 assert query['own']['code']==0 and query['own']['own_buffer_alias']
 owner=next(x for x in ownership if x['process']==query['owner'])
 assert query['peer']['target']==owner['ready']['address']
 # These are observations of this run, not universal error-code expectations.
 assert query['peer']['code']==500 and not query['peer']['own_buffer_alias']
assert counts=={'kernel_operations':6,'buffer_checks':18,'mapping_queries':4},counts
status=json.loads((out/'status.json').read_text());assert status['state']=='CLOSED' and status['failure'] is None and not status['cleanup_errors']
summary={'status':'VERIFIED_NATIVE_PREPARATION',**counts,'same_gpu':True,'separate_host_processes':True,
 'cross_gpu_access_executed':False,'gpu_boundary_verdict':'INCONCLUSIVE','cleanup_verified':True}
(out/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
