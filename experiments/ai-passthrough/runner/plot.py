"""Generate report figures from actual completed measurements only."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
R=Path(__file__).resolve().parents[1];s=json.loads((R/'results/20261016/summary.json').read_text());out=R/'figures';out.mkdir(exist_ok=True)
plt.rcParams.update({'figure.dpi':150,'axes.spines.top':False,'axes.spines.right':False})
rows=[x for x in s['conditions'] if x['n']];names=[x['condition'].replace('-','\n') for x in rows];x=np.arange(len(rows))
fig,ax=plt.subplots(figsize=(12,5))
for offset,mode,color in [(-.18,'passthrough','#4361a8'),(.18,'vmweave','#da8244')]:
 means=[r['backends'][mode]['mean_samples_per_second'] for r in rows];sd=[r['backends'][mode]['sd_samples_per_second'] or 0 for r in rows]
 ax.bar(x+offset,means,.36,yerr=sd,label=mode,color=color,capsize=3)
ax.set_yscale('log');ax.set_ylabel('Samples / second (log scale; mean ± SD)');ax.set_xticks(x,names);ax.legend();ax.set_title('Same GPU, same FP32 training workload');fig.tight_layout();fig.savefig(out/'throughput.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(12,4));ratios=[r['paired_geomean_ratio'] for r in rows]
errors=np.array([[v-r.get('ratio_95ci',[v,v])[0],r.get('ratio_95ci',[v,v])[1]-v] for r,v in zip(rows,ratios)]).T
for i,r in enumerate(rows):
 ax.scatter([i+.04*(j-(r['n']-1)/2) for j in range(r['n'])],[p['ratio'] for p in r['pairs']],s=14,color='#999999',alpha=.7)
ax.errorbar(x,ratios,yerr=errors,fmt='o',capsize=5,color='#b6572a');ax.axhline(1,color='gray',ls='--',label='Parity');ax.set_yscale('log');ax.set_xticks(x,names);ax.set_ylabel('VMWeave / passthrough throughput (log scale)');ax.set_title('Paired geometric mean, 95% t interval, and individual pairs');ax.legend();fig.tight_layout();fig.savefig(out/'ratio.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(12,5))
for offset,mode,color in [(-.18,'passthrough','#4361a8'),(.18,'vmweave','#da8244')]:
 values=[]
 for r in rows:
  v=[q['host_cpu_seconds_per_sample'] for q in s['runs'] if q['backend']==mode and q['condition']==r['condition'] and 'host_cpu_seconds_per_sample' in q];values.append(np.mean(v) if v else float('nan'))
 ax.bar(x+offset,values,.36,label=mode,color=color)
ax.set_yscale('log');ax.set_ylabel('QEMU/Worker Pod process CPU seconds / sample');ax.set_xticks(x,names);ax.legend();fig.tight_layout();fig.savefig(out/'cpu-cost.png');plt.close(fig)
supplement=R/'results/20261016/equal-budget/summary.json'
if supplement.exists():
 eq=json.loads(supplement.read_text());assert all(r['n']==3 for r in eq['conditions'])
 conditions=[r['condition'] for r in eq['conditions']];positions=np.arange(len(conditions))
 fig,ax=plt.subplots(figsize=(8,4))
 for offset,source,label,color in [(-.08,s,'Main: PT 8 vCPU (5 pairs)','#4361a8'),(.08,eq,'Supplement: PT 12 vCPU (3 pairs)','#da8244')]:
  subset=[next(r for r in source['conditions'] if r['condition']==c) for c in conditions]
  means=np.array([r['paired_geomean_ratio']*100 for r in subset]);intervals=np.array([r['ratio_95ci'] for r in subset])*100
  ax.errorbar(positions+offset,means,yerr=[means-intervals[:,0],intervals[:,1]-means],fmt='o',capsize=5,label=label,color=color)
 ax.set_xticks(positions,[c.replace('-','\n') for c in conditions]);ax.set_ylim(bottom=0);ax.set_ylabel('VMWeave / passthrough throughput (%)');ax.set_title('CPU allowance sensitivity; geometric means and 95% t intervals');ax.legend();fig.tight_layout();fig.savefig(out/'equal-budget.png');plt.close(fig)
