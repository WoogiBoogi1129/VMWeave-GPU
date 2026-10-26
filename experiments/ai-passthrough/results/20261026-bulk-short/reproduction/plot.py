import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path('experiments/ai-passthrough/results/20261026-bulk-short');d=json.loads((O/'comparison.json').read_text());plt.rcParams.update({'svg.fonttype':'none','font.size':10})
fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
for ax,w in zip(axes.flat,['nw','lu','srad','sc']):
 rows=[next(r for r in d if r['mode']==m and r['workload']==w) for m in ['flyt','off','on']];v=[r['mean_s'] for r in rows];err=[r['std_s'] or 0 for r in rows];bars=ax.barh(['Flyt SHM','VMWeave OFF','VMWeave ON'],v,xerr=err,capsize=3,color=['#E69F00','#697586','#009E73']);ax.invert_yaxis();ax.bar_label(bars,labels=[f'{x:.4f}s' for x in v],padding=6);ax.set_xlim(0,max(x+y for x,y in zip(v,err))*1.35);ax.set_title(w.upper()+(' — n=1, validation only' if w=='sc' else ' — n=5 in 3 VM sessions'));ax.set_xlabel('Mean completion time (s), lower is better')
fig.suptitle('Compact bulk-copy comparison — one warmup per workload session\nError bars: sample standard deviation; no significance claim')
for ext in ['png','svg']:fig.savefig(O/('runtime.'+ext),dpi=180)
plt.close(fig)
d=json.loads((O/'copy-comparison.json').read_text());fig,axes=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
for ax,direction in zip(axes,['H2D','D2H','D2D']):
 for mode,color in [('off','#697586'),('on','#009E73')]:
  rows=sorted((r for r in d if r['direction']==direction and r['mode']==mode),key=lambda r:r['bytes']);ax.plot([r['bytes'] for r in rows],[r['median_s']*1000 for r in rows],'o-',label=mode.upper(),color=color)
 ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('Bytes (log scale)');ax.set_ylabel('Median completed-copy latency (ms, log scale)');ax.set_title(direction);ax.legend();ax.grid(alpha=.2)
fig.suptitle('Copy sweep — one warmup + five measurements per condition; one session per mode')
for ext in ['png','svg']:fig.savefig(O/('copy-latency.'+ext),dpi=180)
