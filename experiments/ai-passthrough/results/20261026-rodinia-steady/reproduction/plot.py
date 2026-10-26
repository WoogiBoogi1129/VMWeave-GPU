"""Render completed experiment statistics; matplotlib is needed only for plots."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path('experiments/ai-passthrough/results/20261026-rodinia-steady')
data=json.loads((O/'comparison.json').read_text());assert len(data)==16 and all(x['n']==10 for x in data)
modes=['native','passthrough','flyt','vmweave'];labels=['Native','Passthrough','Flyt SHM','VMWeave'];colors=['#697586','#0072B2','#E69F00','#009E73'];workloads=['lu','sc','srad','nw'];titles=['LU (2064)','StreamCluster','SRAD (2048 x 2048, 2 iterations)','NW (2048, penalty 10)']
plt.rcParams.update({'font.size':11,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for ax,w,title in zip(axes.flat,workloads,titles):
 rows=[next(x for x in data if x['workload']==w and x['mode']==m) for m in modes];vals=[r['mean_s'] for r in rows];err=[r['std_s'] for r in rows]
 bars=ax.barh(labels,vals,xerr=err,color=colors,capsize=3);ax.invert_yaxis();ax.bar_label(bars,labels=[f'{v:.4f} s' for v in vals],padding=6,fontsize=9);ax.set_xlim(0,max(v+e for v,e in zip(vals,err))*1.35);ax.set_title(title);ax.set_xlabel('Execution time (seconds; lower is better)');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
fig.suptitle('Rodinia after initialization: mean +/- standard deviation\n10 measured samples in 5 independent sessions; linear scale per panel',fontsize=15)
for extension in ['svg','png']:fig.savefig(O/('runtime.'+extension),dpi=180)
plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
for ax,reference in zip(axes,['native','passthrough']):
 for i,mode in enumerate(['flyt','vmweave']):
  values=[next(x for x in data if x['workload']==w and x['mode']==mode)[reference+'_overhead_pct']/100+1 for w in workloads];positions=[j+(i-.5)*.32 for j in range(4)];bars=ax.bar(positions,values,width=.3,label={'flyt':'Flyt SHM','vmweave':'VMWeave'}[mode],color=colors[2+i]);ax.bar_label(bars,labels=[f'{v:.2f}x' for v in values],padding=4,fontsize=9)
 ax.axhline(1,color='black',ls='--',lw=1);ax.set_yscale('log');ax.set_ylim(bottom=.8);lo,hi=ax.get_ylim();ax.set_ylim(lo,hi*1.6);ax.set_xticks(range(4),['LU','StreamCluster','SRAD','NW']);ax.set_title('Reference: '+reference.capitalize()+' = 1x');ax.set_ylabel('Execution time / reference time (log scale)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend()
fig.suptitle('Normalized execution time (lower is better; 1.15x means +15% time)',fontsize=14)
for extension in ['svg','png']:fig.savefig(O/('normalized.'+extension),dpi=180)
plt.close(fig)
