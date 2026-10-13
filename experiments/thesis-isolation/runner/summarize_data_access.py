"""Audit E2 synthetic-buffer access evidence and export selected, unmodified logs."""
import csv,json,hashlib,tarfile,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];base=ROOT/'experiments/thesis-isolation/results/20261012-campaign';src=base/'data-access-20261013';out=ROOT/'experiments/thesis-isolation/evidence/20261013-e2';out.mkdir(parents=True,exist_ok=True)
trials=json.loads((src/'results.json').read_text());assert len(trials)==40
files=set();rows=[]
for r in trials:
 name=r['name'];d=src/name;approved=d/'approved-target.json';files.add(approved)
 evidence={}
 for slot in ['a','b']:
  p=base/'runs'/(name+'-'+slot)
  for f in ['requests-events.jsonl','cleanup.json']:files.add(p/f)
  assert json.loads((p/'cleanup.json').read_text())['released']
  evidence[slot]=[json.loads(x) for x in (p/'requests-events.jsonl').read_text().splitlines()]
 target,requester=(evidence['a'],evidence['b']) if r['direction']=='ab' else (evidence['b'],evidence['a'])
 access=next(x for x in requester if x['event']=='access');assert access==r['access']
 target_ready=next(x for x in target if x['event']=='ready');own=next(x for x in requester if x['event']=='ready')
 assert target_ready==r['target'] and own==r['requester']
 checks=[x for x in target if x['event']=='check'];assert len(checks)==2 and all(x['code']==0 for x in checks)
 assert not r.get('error') and not r.get('cleanup_errors')
 if r['path'].startswith('raw'):
  assert target_ready['handle']==own['handle'] and access['code']==0
  if r['path']=='rawread':assert access['observed']==own['seed'] and access['observed']!=target_ready['seed']
  outcome='SELF_SESSION_HANDLE; no target modification observed'
 else:
  assert access['launch']==1 and access['sync']==0 and access['copy']==0
  assert access['observed']==own['seed']
  outcome='LAUNCH_REJECTED; GPU cross-access unverified'
 rows.append({'trial':name,'direction':r['direction'],'repetition':r['rep'],'path':r['path'],'outcome':outcome,'target_checks_ok':2,'access_code':access.get('code',access.get('launch')),'observed':access.get('observed'),'target_seed':target_ready['seed'],'requester_seed':own['seed']})
assert all(sum(x['path']==p and x['direction']==d for x in rows)==5 for p in ['rawread','rawwrite','read','write'] for d in ['ab','ba'])
with (out/'trials.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
summary={'experiment':'E2 data access','trials':40,'per_path':dict(collections.Counter(x['path'] for x in rows)),'target_buffer_check_failures':0,'observed_cross_access':0,'released_sessions':80,'api_rejections':0,'kernel_launch_rejections':20,'gpu_cross_access_verified':False,'verdict':'INCONCLUSIVE','rejection_layer':'Guest pointer rejection is supported by source inspection, not independently instrumented at the Worker boundary','write_limit':'API write returned success and target remained intact; requester post-write content was not read back, so own-buffer write is inferred from session-local handle resolution.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
manifest={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(out/'raw-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(out/'raw-evidence.tar.gz','w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p.relative_to(base)),recursive=False)
print(json.dumps(summary,indent=2))
