"""Post-hoc descriptive sensitivity only; no added GPU experiments or new CIs."""
from pathlib import Path
import csv,json,math,statistics
P=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((P/'analysis/blocks.csv').open()))
lookup={(int(r['block']),r['mode'],int(r['id'])):r for r in rows}
out=[]
for id,metric in [(0,'p50_us'),(6,'GiB_s'),(12,'GiB_s'),(15,'kernels_s')]:
 for den in 'FLN':
  ratios=[float(lookup[b,'V',id][metric])/float(lookup[b,den,id][metric]) for b in range(1,6)]
  out.append({'id':id,'metric':metric,'comparison':'V/'+den,'blocks_1_to_4_geometric_ratio':math.exp(statistics.mean(math.log(x) for x in ratios[:4])),'block_5_ratio':ratios[4],'all_5_geometric_ratio':math.exp(statistics.mean(math.log(x) for x in ratios))})
with (P/'analysis/environment-sensitivity.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
(P/'analysis/environment-quality.json').write_text(json.dumps({'scope':'Post-hoc descriptive review prompted by detected shared-node workload changes; not a new experiment or a preregistered hypothesis test.','fixed_benchmark_configuration':True,'unchanged_shared_node_environment':False,'affected_block':5,'primary_analysis':'Retains all 320 completed intervals; does not selectively remove measured values.','causal_limit':'Block 5 coincided with background workload changes. Five-block confidence intervals do not isolate transport causality or quantify that confounding.','comparison':'Geometric paired ratios over blocks 1-4 versus block 5, without additional confidence intervals.'},indent=2)+'\n')
print('ENVIRONMENT_SENSITIVITY_WRITTEN')
