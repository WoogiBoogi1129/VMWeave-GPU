"""Window-filtered endpoint intervals joined by request ID, not mixed clocks."""
from common import *
import csv,gzip,statistics,math
from evidence_io import read_text,exists
os.sched_setaffinity(0,{48,49,50,51})
STAGES={1:'guest_pack',2:'guest_shm_write',3:'worker_allocate',4:'worker_snapshot',5:'guest_exchange_inclusive',6:'worker_dispatch_inclusive',7:'worker_respond',8:'cuda_h2d_api',9:'cuda_d2h_api',10:'cuda_sync_api'}
def stats(x):
 s=sorted(x);n=len(s)
 def quant(p):
  i=(n-1)*p;a=int(i);return s[a]+(s[min(a+1,n-1)]-s[a])*(i-a)
 return {'n':n,'mean':statistics.mean(s),'sd':statistics.stdev(s) if n>1 else None,'p50':quant(.5),'p95':quant(.95),'p99':quant(.99) if n>=10000 else None}
rows=[];stages=[];checks=[]
for run in sorted((OUT/'runs').glob('hd-*')):
 if not (run/'execution.json').exists() or not (run/'cleanup.json').exists():continue
 execution=json.loads((run/'execution.json').read_text())
 if execution['exit_code'] or (run/'failure.json').exists():continue
 condition=json.loads((run/'condition.json').read_text());events=[]
 for line in read_text(run/'stdout.jsonl').splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
 windows=[]
 for e in events:
  if e['event']=='CONDITION':win={'mode':e['mode'],'bytes':e['bytes'],'seconds':e['duration_s'],'warmup_min_s':e['warmup_min_s']}
  if e['event']=='WARMUP_END':win.update({'warmup_elapsed':e['elapsed'],'warmup_completed':e['completed']})
  if e['event']=='MEASUREMENT_START':win['start']=e.get('monotonic');win['utc_start']=e['utc']
  if e['event']=='MEASUREMENT_END':win.update({'end':e.get('monotonic'),'utc_end':e['utc'],'completed':e['completed'],'elapsed':e['elapsed']});windows.append(win.copy())
 records=[];dropped=[]
 for file in [run/'stderr.txt',run/'worker-stream.txt']:
  if not exists(file):continue
  for line in read_text(file).splitlines():
   if line.startswith('HD_BEGIN,'):dropped.append(int(line.split(',')[-1]))
   if not line.startswith('HD,'):continue
   _,role,stage,rid,n,end,ns=line.split(',');records.append({'role':role,'stage':int(stage),'id':int(rid),'bytes':int(n),'end':int(end),'ns':int(ns)})
 for w in windows:
  paths=list(run.glob('*-'+w['mode']+'-'+str(w['bytes'])+'.csv.gz'))
  if not paths:paths=list(run.glob(run.name+'.csv.gz'))
  assert len(paths)==1,(run,w,paths)
  with gzip.open(paths[0],'rt') as f:samples=list(csv.DictReader(f))
  assert len(samples)==w['completed']
  for i,s in enumerate(samples):
   assert int(s['sample'])==i and all(math.isfinite(float(v)) and float(v)>=0 for k,v in s.items() if k!='sample')
   if 'h2d_copy_s' in s:
    assert abs(float(s['first_seconds'])-float(s['h2d_copy_s'])-float(s['h2d_sync_s']))<3e-9
    assert abs(float(s['second_seconds'])-float(s['d2h_copy_s'])-float(s['d2h_sync_s']))<3e-9
  row={'run':run.name,**condition,'mode':w['mode'],'bytes':w['bytes'],'seconds':w['seconds'],'warmup_min_s':w['warmup_min_s'],'warmup_elapsed':w['warmup_elapsed'],'warmup_completed':w['warmup_completed'],'completed':len(samples),'rate':len(samples)/w['elapsed'],'elapsed':w['elapsed'],'utc_start':w['utc_start'],'utc_end':w['utc_end']}
  for key in samples[0]:
   if key=='sample':continue
   values=[float(s[key])*1000 for s in samples]
   row[key]=stats(values)
   quarter=max(1,len(values)//4)
   row[key]['first_quarter_mean']=statistics.mean(values[:quarter])
   row[key]['last_quarter_mean']=statistics.mean(values[-quarter:])
  rows.append(row)
  if not records or w['start'] is None:continue
  selected=[r for r in records if r['stage']==2 and r['bytes']==w['bytes']+48 and r['end']-r['ns']>=w['start']*1e9 and r['end']<=w['end']*1e9]
  ids={r['id'] for r in selected};assert len(ids)==w['completed'],(run,len(ids),w['completed'])
  result={'run':run.name,'variant':condition['variant'],'mode':w['mode'],'worker_cpus':condition.get('worker_cpus','16-19'),'bytes':w['bytes'],'ids':len(ids),'stages_ms':{}}
  for stage in [1,2,3,4,5,6,7,8]:
   group=[r for r in records if r['stage']==stage and r['id'] in ids]
   assert len(group)==len(ids),(run,stage,len(group),len(ids))
   result['stages_ms'][STAGES[stage]]=stats([r['ns']/1e6 for r in group])
  stages.append(result)
 checks.append({'run':run.name,'samples_valid':True,'dropped_records':sum(dropped),'all_results_pass':all(e['status']=='PASS' and e['mismatches']==0 for e in execution['results'])})
 assert not sum(dropped)
save(OUT/'analysis.json',{'rows':rows,'stages':stages,'checks':checks,'units':'all latency stats in ms; independent repetition is a session, not request','nested_stages':['guest_exchange_inclusive','worker_dispatch_inclusive']})
for s in stages:
 if s['bytes']==16777216:print(s['run'],{k:round(v['mean'],4) for k,v in s['stages_ms'].items()})
