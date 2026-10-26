"""Offline sensitivity to the interruption; never changes the primary sample set."""
import json,statistics
from pathlib import Path
O=Path('experiments/ai-passthrough/results/20261026-rodinia-steady');rows=[]
for p in sorted((O/'formal').glob('r[2-5]/*/*/result.json')):
 r=json.loads(p.read_text());assert r['correct'] and r['returncode']==0
 for a in r['samples']:
  if not a['warmup']:rows.append({'mode':r['mode'],'workload':r['workload'],'seconds':a['seconds']})
out=[]
for w in ['nw','lu','srad','sc']:
 by={m:[r['seconds'] for r in rows if r['mode']==m and r['workload']==w] for m in ['native','passthrough','flyt','vmweave']}
 assert all(len(v)==8 for v in by.values())
 for m,v in by.items():
  avg=statistics.mean(v);out.append({'workload':w,'mode':m,'n':8,'sessions':['r2','r3','r4','r5'],'mean_s':avg,'native_overhead_pct':100*(avg/statistics.mean(by['native'])-1),'passthrough_overhead_pct':100*(avg/statistics.mean(by['passthrough'])-1)})
(O/'resumed-only-comparison.json').write_text(json.dumps(out,indent=2))
