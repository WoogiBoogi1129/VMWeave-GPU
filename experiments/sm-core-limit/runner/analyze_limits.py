"""Summarize independent VM runs (run means, not pseudoreplicated samples)."""
import csv, json, statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'evidence/limit-validation-20261015'
rows=[]
fig,grid=plt.subplots(2,2,figsize=(12,8))
axes=list(grid.flat)
for cap,color in [(25,'tab:blue'),(50,'tab:orange'),(75,'tab:green')]:
    runs=[]
    ax=axes[{25:1,50:2,75:3}[cap]]
    for folder in sorted(OUT.glob(f'run-*-limit-{cap}')):
        r=json.loads((folder/'result.json').read_text())
        samples=list(csv.reader((folder/'gpu.csv').open()))
        t=[float(s[0]) for s in samples];u=[float(s[1]) for s in samples]
        kept=[v for x,v in zip(t,u) if x>=32]
        assert abs(statistics.mean(kept)-r['device_util_mean'])<1e-8
        runs.append(r)
        rows.append(dict(run=folder.name,limit=cap,utilization=r['device_util_mean'],error_pp=r['device_util_mean']-cap,launches_per_second=r['launches_per_second'],samples=len(kept),sample_min=min(kept),sample_max=max(kept)))
        ax.plot(t,u,color=color,alpha=.13,linewidth=.7)
        smooth=[statistics.mean(u[max(0,i-9):i+1]) for i in range(len(u))]
        ax.plot(t,smooth,color=color,alpha=.8,linewidth=1)
    assert len(runs)==3,(cap,len(runs))
    means=[r['device_util_mean'] for r in runs]
    axes[0].errorbar(cap,statistics.mean(means),yerr=statistics.stdev(means),fmt='o',color=color,capsize=5,label=f'{cap}% (n=3)')
    axes[0].scatter([cap]*3,means,color=color,s=12,alpha=.5)
    ax.axhline(cap,color='black',linestyle='--',linewidth=1,label=f'{cap}% target')
    ax.axvspan(0,32,color='gray',alpha=.15)
    ax.set(title=f'Limit {cap}%: 3 runs',xlabel='Elapsed seconds',ylabel='GPU utilization (%)',ylim=(0,105))
    ax.legend();ax.grid(alpha=.2)
summary=[]
for cap in [25,50,75]:
    rr=[r for r in rows if r['limit']==cap];means=[r['utilization'] for r in rr]
    summary.append(dict(limit=cap,mean_utilization=statistics.mean(means),run_sd=statistics.stdev(means),run_min=min(means),run_max=max(means),error_pp=statistics.mean(means)-cap,mean_launches_per_second=statistics.mean(r['launches_per_second'] for r in rr)))
(OUT/'summary.json').write_text(json.dumps(dict(runs=rows,summary=summary),indent=2)+'\n')
with (OUT/'summary.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
axes[0].plot([0,100],[0,100],'k--',alpha=.5,label='Target');axes[0].set(xlabel='Configured limit (%)',ylabel='Mean GPU utilization (%)',xlim=(10,90),ylim=(10,90));axes[0].legend();axes[0].grid(alpha=.2)
fig.suptitle('VMWeave SM limits: 3 independent runs per limit\nTime series: faint raw samples, solid 10-sample moving means')
fig.tight_layout();fig.savefig(OUT/'limits.png',dpi=180);fig.savefig(OUT/'limits.pdf')
print(json.dumps(summary,indent=2))
