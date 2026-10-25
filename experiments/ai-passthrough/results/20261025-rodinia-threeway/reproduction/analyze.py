import csv,json,statistics
from pathlib import Path
import rodinia_campaign as h
rows=[]
for p in sorted((h.O/'formal').glob('*/*/result.json')):
 for r in json.loads(p.read_text()):
  mode=p.parent.name;round=p.parent.parent.name
  rows.append({'round':round,'mode':mode,'workload':r['workload'],'seconds':r['timing']['seconds'],'startup_seconds':r['timing']['startup_seconds'],'gpu_phase_seconds':r['timing']['gpu_phase_seconds'],'correct':r.get('correct',r.get('matches_native_reference',False)),'sha256':r['sha256'],'log':str(p.relative_to(h.O))})
with (h.O/'raw.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert len(rows)==18 and all(r['correct'] for r in rows)
stats=[]
for workload in ['nw','lud2064']:
 baseline=statistics.median(r['seconds'] for r in rows if r['workload']==workload and r['mode']=='passthrough')
 for mode in ['passthrough','flyt','vmweave']:
  x=[r['seconds'] for r in rows if r['workload']==workload and r['mode']==mode];assert len(x)==3
  med=statistics.median(x);cv=statistics.stdev(x)/statistics.mean(x);ratio=baseline/med
  stats.append({'workload':workload,'mode':mode,'n':3,'median_seconds':med,'min_seconds':min(x),'max_seconds':max(x),'sample_cv':cv,'throughput_relative_to_passthrough_percent':ratio*100,'diagnostic_required':mode!='passthrough' and (med>baseline*1.2 or cv>.1 or all(next(t['seconds'] for t in rows if t['round']==r['round'] and t['mode']=='passthrough' and t['workload']==workload)>r['seconds'] for r in rows if r['mode']==mode and r['workload']==workload))})
h.save(h.O/'comparison.json',stats);print(json.dumps(stats,indent=2))
