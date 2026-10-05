from common import *
import statistics
os.sched_setaffinity(0,{48,49,50,51})
a=json.loads((OUT/'analysis.json').read_text());cpu={ (r['run'],r['mode'],r['bytes']):r for r in json.loads((OUT/'cpu-analysis.json').read_text())['rows']}
def phase(run):
 if run.startswith('hd-main-r'):return 'main-initial'
 for p in ['main','cause','confirm','pattern','numa']:
  if run.startswith('hd-'+p+'-'):return p
 return 'pilot/'+run
def summary(values):
 return {'repeats':len(values),'mean':statistics.mean(values),'sd':statistics.stdev(values) if len(values)>1 else None}
groups={}
for r in a['rows']:
 group=(phase(r['run']),r['path'],r['variant'],r['metrics'],r['mode'],r['bytes'],r.get('worker_cpus','16-19'))
 groups.setdefault(group,[]).append(r)
result=[]
for key,rows in sorted(groups.items()):
 p,path,variant,metrics,mode,n,cpus=key
 g={'worker_cpus':cpus,'phase':p,'path':path,'variant':variant,'metrics':metrics,'mode':mode,'bytes':n,'runs':[r['run'] for r in rows]}
 for k in ['first_seconds','second_seconds','h2d_copy_s','h2d_sync_s','d2h_copy_s','d2h_sync_s']:
  if k not in rows[0]:continue
  g[k]={stat:summary([r[k][stat] for r in rows]) for stat in ['mean','p50','p95']}
 g['operations_per_s']=summary([r['rate'] for r in rows]);g['sample_counts']=[r['completed'] for r in rows]
 c=[cpu.get((r['run'],r['mode'],r['bytes'])) for r in rows]
 if all(x and x['cores'] is not None for x in c):
  g['cpu_cores']=summary([x['cores'] for x in c]);g['cpu_us_iteration']=summary([x['cpu_us_iteration'] for x in c]);g['min_cpu_coverage']=min(v['coverage'] for x in c for v in x['parts'].values())
 result.append(g)
sg={}
for s in a['stages']:
 key=(phase(s['run']),s['variant'],s['bytes'],s.get('mode','copy'),s.get('worker_cpus','16-19'))
 sg.setdefault(key,[]).append(s)
stages=[]
for (p,v,n,m,cpus),items in sorted(sg.items()):
 stages.append({'worker_cpus':cpus,'phase':p,'variant':v,'bytes':n,'mode':m,'runs':[r['run'] for r in items],'stages_ms':{k:summary([r['stages_ms'][k]['mean'] for r in items]) for k in items[0]['stages_ms']}})
save(OUT/'summary.json',{'groups':result,'stages':stages,'statistical_unit':'independent VM session mean; samples are not independent repetitions','latency_units':'ms','nested_stage_warning':'exchange and dispatch overlap other intervals; never sum all columns.'})
for g in result:
 if not g['phase'].startswith('pilot') and g['bytes']==16777216:print(g['phase'],g['path'],g['variant'],g['metrics'],g['first_seconds']['mean'])
