"""Post-hoc sensitivity to the observed shared-host service change in block 2."""
import json,math,statistics
from pathlib import Path
E=Path(__file__).resolve().parents[1]/'results/20261016'
source=json.loads((E/'summary.json').read_text())
rows=[]
for condition in source['conditions']:
 assert condition['n']==5
 pairs=[p for p in condition['pairs'] if p['block']!=2]
 assert len(pairs)==4
 logs=[math.log(p['ratio']) for p in pairs]
 mean=statistics.mean(logs);half=3.182*statistics.stdev(logs)/2
 rows.append({'condition':condition['condition'],'n':4,'pairs':pairs,
  'all_five_ratio':condition['paired_geomean_ratio'],
  'excluding_block2_ratio':math.exp(mean),
  'excluding_block2_95ci':[math.exp(mean-half),math.exp(mean+half)]})
result={'post_hoc':True,'excluded_block':2,'reason':'Observed GPU 3 embedding service scale-down/up during block 2 VMWeave; original five-block results remain primary. This does not isolate the causal effect of the service change.','conditions':rows}
(E/'sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(rows,indent=2))
