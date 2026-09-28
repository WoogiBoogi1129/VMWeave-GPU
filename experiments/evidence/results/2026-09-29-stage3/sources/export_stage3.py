"""Export original Stage3 observations, CSVs, Prometheus queries and Grafana annotations."""
import argparse,base64,csv,gzip,json,shutil,urllib.parse,urllib.request
from pathlib import Path
from verify_stage3 import verify_pair
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.output;mon=root/'monitoring';mon.mkdir(exist_ok=True)
def save(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def csvout(p,rows):
 with p.open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');writer.writeheader();writer.writerows(rows)
auth=json.loads((a.base/'grafana-auth.json').read_text());headers={'Authorization':'Basic '+base64.b64encode((auth['user']+':'+auth['password']).encode()).decode(),'Content-Type':'application/json'}
annotations=[];summary=[];allocs=[];progress=[];queries=[]
metrics=['s3_live_bytes','s3_limit_bytes','s3_hami_memory_bytes','s3_completed_checks_total','s3_mismatches_total','s3_oom_total','s3_gpu_total_memory_bytes','s3_collector_errors','s3_collector_timestamp_seconds','up{job="stage3"}']
for pair in sorted(root.glob('pair-*')):
 v=verify_pair(pair);save(pair/'validation.json',v);summary.append(v)
 phases=json.loads((pair/'phases.json').read_text());begin=next(x['host_utc'] for x in phases if x['phase']=='BOTH_READY')-5;end=next(x['host_utc'] for x in phases if x['phase']=='BOTH_COMPLETE')+5
 save(pair/'plot-window.json',{'start':begin,'end':end,'clock':'host UTC, observed after program event'})
 for ph in phases:
  if ph['phase'] in ['PREPARED','RELEASED']:continue
  labels={'BOTH_READY':'Both VMs: precheck passed', 'B_LARGE_ALLOCATED':'B: 1536 MiB allocated', 'A_EXPECTED_OOM':'A: 1536 MiB rejected (CUDA OOM)', 'A_SMALL_ALLOCATED':'A: 128 MiB allocated in the same session', 'A_FREED':'A: verification passed; 128 MiB freed', 'B_FREED':'B: verification passed; 1536 MiB freed', 'BOTH_COMPLETE':'Both VMs: normal program exit'}
  ann={'time':int(ph['host_utc']*1000),'tags':['stage3',pair.name],'text':labels[ph['phase']]}
  req=urllib.request.Request('http://127.0.0.1:3301/api/annotations',data=json.dumps(ann).encode(),headers=headers,method='POST')
  with urllib.request.urlopen(req,timeout=10) as response:ann['created']=json.load(response)
  annotations.append(ann)
 for metric in metrics:
  query=metric+'{pair="'+pair.name+'"}' if metric.startswith('s3_') and metric not in metrics[6:9] else metric
  params={'query':query,'start':begin,'end':end,'step':1}
  with urllib.request.urlopen('http://127.0.0.1:9098/api/v1/query_range?'+urllib.parse.urlencode(params),timeout=30) as r:data=json.load(r)
  assert data['status']=='success' and data['data']['result'],(pair.name,query,'no samples')
  name=pair.name+'-'+metric.split('{')[0]+'.json';save(mon/name,data);queries.append({'pair':pair.name,'file':name,**params})
 for role in ['A','B']:
  receipts=[json.loads(s) for s in (pair/role/'host-receipts.jsonl').read_text().splitlines()]
  for x in receipts:
   binding=json.loads((pair/role/'trace-binding.json').read_text())
   row={'pair':pair.name,**binding,'host_received_utc':x['host_received_utc'],**x['record']}
   if row['event'] in ['ALLOC','FREE']:allocs.append(row)
   if row['event']=='PROGRESS':progress.append(row)
 # Two genuine B progress records immediately after A's OOM and small-allocation events.
 aa=[json.loads(s) for s in (pair/'A/host-receipts.jsonl').read_text().splitlines()];bb=[json.loads(s) for s in (pair/'B/host-receipts.jsonl').read_text().splitlines()];excerpt=[]
 for phase in ['large','small']:
  stamp=next(x['host_received_utc'] for x in aa if x['record']['event']=='ALLOC' and x['record']['phase']==phase)
  chosen=next(x for x in bb if x['host_received_utc']>stamp and x['record']['event']=='PROGRESS')
  excerpt.append({'A_event':'OOM' if phase=='large' else '128 MiB success',**chosen})
 (pair/'B/continuation-excerpt.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in excerpt))
save(mon/'annotations.json',annotations);save(mon/'queries.json',queries);save(root/'summary.json',summary)
csvout(root/'allocation-events.csv',allocs);csvout(root/'progress.csv',progress)
csvout(root/'summary.csv',[{'pair':x['pair'],'vm':vm,**{k:v for k,v in r.items() if not isinstance(v,(dict,list))}} for x in summary for vm,r in x['roles'].items()])
(mon/'observations.jsonl.gz').write_bytes(gzip.compress((a.base/'observations.jsonl').read_bytes(),mtime=0))
for name in ['prometheus.yml','grafana.ini']:shutil.copy2(a.base/'monitoring'/name,mon/name)
for sub in ['dashboards','provisioning']:shutil.copytree(a.base/'monitoring'/sub,mon/sub,dirs_exist_ok=True)
for url,name in [('http://127.0.0.1:3301/api/health','grafana-version.json'),('http://127.0.0.1:9098/api/v1/status/buildinfo','prometheus-version.json')]:
 with urllib.request.urlopen(url) as r:save(mon/name,json.load(r))
print('Exported 3 pairs, original metrics and annotations; no video')
