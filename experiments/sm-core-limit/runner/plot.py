"""Standalone evidence plots; raw samples plus 10-sample moving means."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'experiments/sm-core-limit/evidence'
fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
colors={'original':'#ba3a32','patched':'#2461a6','idle-reset':'#168069'}
for ax,title,paths in [(axes[0],'Native CUDA, limit 50%',list((E/'long-kernel-v2').glob('*/result.json'))+list((E/'idle-long').glob('*/result.json'))),
                       (axes[1],'VMWeave Guest -> SHM -> Worker, limit 50%',list((E/'vmweave/runs').glob('*/result.json')))]:
    for path in paths:
        result=json.loads(path.read_text());data=[[float(v) for v in line.split(',')] for line in (path.parent/'gpu.csv').read_text().splitlines()]
        if max(r[0] for r in data)<140:continue
        x=[r[0] for r in data];y=[r[1] for r in data];c=colors[result['variant']]
        smooth=[sum(y[max(0,i-9):i+1])/len(y[max(0,i-9):i+1]) for i in range(len(y))]
        ax.plot(x,y,color=c,alpha=.12,linewidth=.7)
        ax.plot(x,smooth,color=c,label=result['variant'],linewidth=1.7)
    ax.axhline(50,color='#444444',linestyle='--',linewidth=1,label='configured limit')
    ax.axvspan(0,30,color='gray',alpha=.1)
    ax.set(title=title,ylabel='Device utilization (%)',ylim=(-2,105));ax.grid(alpha=.2);ax.legend(loc='lower right')
axes[1].set_xlabel('Seconds after probe process start (gray: first 30 seconds)')
fig.suptitle('HAMi-core SM limiter: single-run exploratory measurements\nFaint: raw ~1 s samples; solid: 10-sample moving mean',fontsize=12)
fig.tight_layout();fig.savefig(E/'utilization-comparison.png',dpi=180);fig.savefig(E/'utilization-comparison.pdf')
