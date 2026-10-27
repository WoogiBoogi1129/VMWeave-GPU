import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path('experiments/ai-passthrough/results/20261027-path-optimization-vm')
d=json.loads((O/'comparison.json').read_text());plt.rcParams.update({'svg.fonttype':'none','font.size':10})
fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
for ax,w in zip(axes.flat,['nw','lu','srad','sc']):
 rows=[next(r for r in d['raw_workload_summary'] if r['mode']==m and r['workload']==w) for m in ['flyt','control','candidate']]
 vals=[r['median_s'] for r in rows];bars=ax.barh(['Flyt SHM','VMWeave control','VMWeave candidate'],vals,color=['#E69F00','#697586','#009E73'])
 bound=max(max(r['session_medians_s']) for r in rows)
 for i,r in enumerate(rows):
  ax.scatter(r['session_medians_s'],[i+j for j in [-.12,-.06,0,.06,.12]],color='#152238',s=18,zorder=3)
  ax.text(max(r['session_medians_s'])+bound*.025,i,f'{vals[i]:.4f}s',va='center')
 ax.invert_yaxis();ax.set_xlim(0,bound*1.3);ax.set_xlabel('Completion time (s), lower is better');ax.set_title(w.upper())
fig.suptitle('Actual VM / ivshmem comparison\nBars: median of 5 VM sessions; dots: each independent VM session')
for ext in ['png','svg','pdf']:fig.savefig(O/('workloads.'+ext),dpi=180)
plt.close(fig)
fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
comparisons=[(r['workload'].upper(),r['candidate_vs_flyt']) for r in d['workloads']]+[('Overall geometric mean',d['overall_candidate_vs_flyt'])]
for i,(name,r) in enumerate(comparisons):
 ax.plot(r['ci95'],[i,i],color='#263b53',linewidth=2)
 ax.plot(r['ratio'],i,'o',color='#009E73' if r['ci95'][1]<1 else '#b04a38' if r['ci95'][0]>1 else '#697586')
 ax.text(2.25,i,f"{r['ratio']:.3f} [{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}]",va='center',fontsize=9)
ax.axvline(1,color='#222222',linestyle='--',linewidth=1)
ax.set_yticks(range(len(comparisons)),[x[0] for x in comparisons]);ax.invert_yaxis();ax.set_xlim(.45,3.35)
ax.set_xlabel('Candidate / Flyt completion-time ratio (lower is better)')
ax.set_title('Paired round geometric ratios and 95% bootstrap intervals\n5 independent VM rounds; intervals crossing 1 do not establish superiority')
for ext in ['png','svg','pdf']:fig.savefig(O/('ratios.'+ext),dpi=180)
plt.close(fig)
d=json.loads((O/'micro-comparison.json').read_text());fig,axes=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
for ax,op in zip(axes,['H2D','D2H','D2D']):
 rows=sorted([r for r in d if r['operation']==op],key=lambda r:r['bytes'])
 for mode,color in [('flyt','#E69F00'),('control','#697586'),('candidate','#009E73')]:ax.plot([r['bytes'] for r in rows],[r['median_ms'][mode] for r in rows],'-o',label=mode,color=color)
 ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_title(op);ax.set_xlabel('Payload bytes');ax.set_ylabel('Completion time (ms)');ax.grid(alpha=.25);ax.legend()
fig.suptitle('Copy latency including explicit completion — median of 5 VM sessions')
for ext in ['png','svg','pdf']:fig.savefig(O/('copy-latency.'+ext),dpi=180)
