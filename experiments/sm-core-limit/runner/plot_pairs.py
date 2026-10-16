"""Export figures from audited concurrent-VM observations."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/sm-core-limit/evidence/pairs-20261016';D=OUT/'figures';D.mkdir(exist_ok=True)
s=json.loads((OUT/'summary.json').read_text());colors={25:'#2563eb',75:'#e66a24'}
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
f,axes=plt.subplots(3,1,figsize=(12,10),sharex=True)
for ax,p in zip(axes,s['pairs']):
 for series in p['series']:
  cap=series['cap'];xy=series['samples'];ax.plot([x[0] for x in xy],[x[1] for x in xy],label=f"VM {series['slot'].upper()} — cap {cap}%",color=colors[cap],alpha=.8,lw=1.3)
 for cap in [25,75]:ax.axhline(cap,color=colors[cap],ls='--',alpha=.65)
 ax.axvspan(0,35,color='#94a3b8',alpha=.15);ax.axvspan(178,185,color='#94a3b8',alpha=.15)
 ax.set(title=f"{p['pair']}: Worker SM utilization (HAMi)",ylabel='SM utilization (%)',ylim=(0,105),xlim=(0,185));ax.legend(loc='upper right',ncol=2);ax.grid(alpha=.15)
axes[-1].set_xlabel('Seconds from coordinated start; shaded regions excluded from steady-window means')
f.tight_layout()
for ext in ['png','pdf']:f.savefig(D/f'worker-utilization.{ext}',dpi=170)
plt.close(f)
f,axes=plt.subplots(1,3,figsize=(14,4.5))
for ax,key,title,ylabel in zip(axes,['hami_util_mean','pmon_util_mean','throughput_share_pct'],['HAMi Worker utilization','pmon (numeric samples only)','Share of completed launches'],['GPU utilization (%)','GPU utilization (%)','Throughput share (%)']):
 for idx,cap in enumerate([25,75]):
  r=next(a for a in s['aggregate'] if a['cap']==cap)
  ax.bar(idx,r[key],yerr=r[key+'_sd'],color=colors[cap],alpha=.85,capsize=5)
  vals=[w[key] for p in s['pairs'] for w in p['workers'] if w['cap']==cap]
  ax.scatter([idx-.07,idx,idx+.07],vals,color='black',s=18,zorder=4)
  ax.text(idx,r[key]+r[key+'_sd']+3,f'{r[key]:.2f}%',ha='center')
 ax.set(xticks=[0,1],xticklabels=['25% cap','75% cap'],ylim=(0,100),ylabel=ylabel,title=title);ax.grid(axis='y',alpha=.15)
f.suptitle('Patched VMWeave: 3 fresh VM pairs, mean ± sample SD; dots = independent trials')
f.tight_layout()
for ext in ['png','pdf']:f.savefig(D/f'quota-vs-observed.{ext}',dpi=170)
plt.close(f)
