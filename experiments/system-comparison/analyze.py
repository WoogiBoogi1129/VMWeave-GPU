"""Aggregate independent sessions, never treat request samples as repetitions."""
from common import *
import csv,gzip,math,statistics

rows=[]
for run in sorted((OUT/'runs').glob('sc-*')):
 if not (run/'execution.json').exists():continue
 execution=json.loads((run/'execution.json').read_text())
 if execution['exit_code']:continue
 condition=json.loads((run/'condition.json').read_text())
 for file in sorted(run.glob('*.csv.gz')):
  mode,size=file.name.removeprefix(run.name+'-').removesuffix('.csv.gz').rsplit('-',1)
  result=next(r for r in execution['results'] if r['mode']==mode and r['bytes']==int(size))
  fields=['first_seconds','second_seconds'] if mode=='copy' else ['first_seconds' if mode=='query' else 'second_seconds']
  values=[[] for _ in fields]
  with gzip.open(file,'rt') as f:
   for i,r in enumerate(csv.DictReader(f)):
    assert int(r['sample'])==i
    for xs,field in zip(values,fields):
     value=float(r[field])*1e6;assert math.isfinite(value) and value>0;xs.append(value)
  assert len(values[0])==result['completed'] and result['status']=='PASS' and result['mismatches']==0
  for index,xs in enumerate(values):
   xs.sort();q=lambda p:xs[int((len(xs)-1)*p)]
   metric=(['h2d','d2h'][index]+'-'+size) if mode=='copy' else mode
   rows.append({'run':run.name,'system':condition['path'],'metric':metric,'count':len(xs),'mean_us':statistics.mean(xs),'p50_us':q(.5),'p95_us':q(.95),'p99_us':q(.99) if len(xs)>=10000 else None,'throughput_s':result['operations_per_s'],'effective_mib_s':int(size)/(statistics.mean(xs)/1e6)/1048576 if mode=='copy' else None})
summary={}
for system in ['T','S']:
 selected=[r for r in rows if r['system']==system and r['run'].startswith('sc-r')];summary[system]={}
 for metric in sorted({r['metric'] for r in selected}):
  group=[r for r in selected if r['metric']==metric];v=[r['mean_us'] for r in group]
  summary[system][metric]={'repeats':len(v),'mean_us':statistics.mean(v),'sd_us':statistics.stdev(v) if len(v)>1 else None,'mean_p95_us':statistics.mean(r['p95_us'] for r in group),'mean_p99_us':statistics.mean(r['p99_us'] for r in group) if all(r['p99_us'] is not None for r in group) else None}
complete=all(len(summary[s])==13 and all(x['repeats']==5 for x in summary[s].values()) for s in summary)
save(OUT/'summary.json',{'rows':rows,'summary':summary,'complete':complete})
print('Complete:',complete)
for system in summary:print(system,{m:round(r['mean_us'],3) for m,r in summary[system].items()})
for r in rows:
 if 'pilot' in r['run']:print(r['run'],r['metric'],round(r['mean_us'],3),r['count'])
