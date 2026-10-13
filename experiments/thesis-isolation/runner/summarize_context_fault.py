"""Audit E3 timing, real CUDA faults, observer results and cleanup evidence."""
import csv,json,hashlib,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];base=ROOT/'experiments/thesis-isolation/results/20261012-campaign';src=base/'context-fault-20261013';out=ROOT/'experiments/thesis-isolation/evidence/20261013-e3';out.mkdir(parents=True,exist_ok=True)
trials=json.loads((src/'results.json').read_text());assert len(trials)==10
files={src/'protocol.json',src/'results.json',src/'status.json'};rows=[];worker_evidence=[]
for r in trials:
 name=r['name'];p=src/name;before=json.loads((p/'baseline.json').read_text());after=json.loads((p/'observer.json').read_text());fault=json.loads((p/'fault.json').read_text())
 f=next(x for x in fault if x['event']=='fault');assert f==r['fault'] and f['load']==0 and f['abi']==0 and f['launch']==0 and f['sync']==700
 pre=[x for x in before if x['event']=='request'];post=[x for x in after if x['event']=='request']
 for seq in [pre,post]:
  assert seq and [x['id'] for x in seq]==list(range(len(seq)))
  assert all(x['code']==0 and 0<=x['latency_s']<40 for x in seq)
 pre_span=pre[-1]['start']+pre[-1]['latency_s']-pre[0]['start'];assert pre_span>=60
 post_span=post[-1]['received_host_utc']-f['received_host_utc'];assert post_span>=60
 assert before[-1]['received_host_utc']<=f['received_host_utc']
 assert len(post)==r['observer_requests'] and r['status']=='PASS' and not r.get('cleanup_errors')
 slot='a' if r['direction']=='ab' else 'b';run=base/'runs'/(name+'-'+slot)
 identity=json.loads((run/'worker-identity.json').read_text());worker=json.loads((p/'observer-worker-after.json').read_text())
 assert worker['metadata']['uid']==identity['uid'] and worker['status']['phase']=='Running'
 assert all(c['ready'] and c['restartCount']==0 for c in worker['status']['containerStatuses'])
 worker_evidence.append({'trial':name,'uid_before':identity['uid'],'uid_after':worker['metadata']['uid'],'phase':worker['status']['phase'],'ready':True,'restarts':0,'source_sha256':hashlib.sha256((p/'observer-worker-after.json').read_bytes()).hexdigest()})
 for slot in ['a','b']:
  d=base/'runs'/(name+'-'+slot);assert json.loads((d/'cleanup.json').read_text())['released'];files.add(d/'cleanup.json')
 for n in ['baseline.json','observer.json','fault.json','verdict.json']:files.add(p/n)
 rows.append({'trial':name,'direction':r['direction'],'baseline_requests':len(pre),'fault_window_requests':len(post),'cuda_sync_error':700,'baseline_span_s':pre_span,'last_completion_after_fault_s':post_span,'max_request_latency_s':max(x['latency_s'] for x in pre+post),'observer_errors':0,'mismatches':0,'observed_timeouts':0,'worker_alive':True,'status':'PASS'})
assert sum(x['direction']=='ab' for x in rows)==5 and sum(x['direction']=='ba' for x in rows)==5
with (out/'trials.csv').open('w') as stream:
 w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
summary={'experiment':'E3 context fault propagation','trials':10,'pass':10,'baseline_requests':sum(x['baseline_requests'] for x in rows),'fault_window_requests':sum(x['fault_window_requests'] for x in rows),'observer_errors':0,'mismatches':0,'observed_timeouts':0,'min_completion_span_after_fault_s':min(x['last_completion_after_fault_s'] for x in rows),'released_sessions':20,'scope':'No propagation observed for the tested single null-store CUDA error 700 and bounded observation window. Fault window starts just before injection; its requests are not all strictly post-fault.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'worker-audit.json').write_text(json.dumps(worker_evidence,indent=2)+'\n')
manifest={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(out/'raw-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(out/'raw-evidence.tar.gz','w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p.relative_to(base)),recursive=False)
print(json.dumps(summary,indent=2))
