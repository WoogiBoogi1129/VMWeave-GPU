import json,csv,statistics,math
from pathlib import Path
R=Path.cwd();O=R/'experiments/ai-passthrough/results/20261026-rodinia-steady';rows=[]
for p in sorted((O/'formal').glob('*/*/*/result.json')):
 r=json.loads(p.read_text());assert r['correct'] and r['returncode']==0,p
 for sample in r['samples']:
  if not sample['warmup']:
   assert math.isfinite(sample['seconds']) and sample['seconds']>0
   rows.append({'session':p.parents[2].name,'mode':r['mode'],'workload':r['workload'],'iteration':sample['iteration'],'seconds':sample['seconds']})
if rows:
 with (O/'raw.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
stats=[]
for workload in ['nw','lu','srad','sc']:
 by={mode:[r['seconds'] for r in rows if r['workload']==workload and r['mode']==mode] for mode in ['native','passthrough','flyt','vmweave']}
 for mode,x in by.items():
  if not x:continue
  mean=statistics.mean(x);stats.append({'workload':workload,'mode':mode,'n':len(x),'mean_s':mean,'median_s':statistics.median(x),'std_s':statistics.stdev(x) if len(x)>1 else None,'min_s':min(x),'max_s':max(x),'native_overhead_pct':100*(mean/statistics.mean(by['native'])-1) if by['native'] else None,'passthrough_overhead_pct':100*(mean/statistics.mean(by['passthrough'])-1) if by['passthrough'] else None})
(O/'comparison.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2))
