"""Standalone research figures from independent-run means and SD."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
s=json.loads((OUT/'summary.json').read_text());assert s['complete'];s=s['summary']
dest=OUT/'figures';dest.mkdir(exist_ok=True)
colors=['#737b8b','#417ac4','#46a18c','#b97530']
variants=['base','wait','copy','both'];names=['Legacy settings','Short sleeps only','Copy changes only','Combined']
for filename,metrics,labels,scale,unit in [
 ('small-latency',['query','kernel','h2d-4096','d2h-4096'],['Query','Launch + sync','H2D 4 KiB + sync','D2H 4 KiB + sync'],1,'Latency (microseconds)'),
 ('large-latency',['h2d-1048576','d2h-1048576','h2d-16777216','d2h-16777216'],['H2D 1 MiB','D2H 1 MiB','H2D 16 MiB','D2H 16 MiB'],.001,'Latency (milliseconds; copy + sync)')]:
 fig,ax=plt.subplots(figsize=(11,5));x=np.arange(len(metrics));width=.19
 for i,(v,name,color) in enumerate(zip(variants,names,colors)):
  values=[s[v][m]['mean_us']*scale for m in metrics];errors=[s[v][m]['sd_us']*scale for m in metrics]
  bars=ax.bar(x+(i-1.5)*width,values,width,yerr=errors,capsize=3,label=name,color=color)
  ax.bar_label(bars,labels=[f'{z:.1f}' for z in values],padding=5,fontsize=8)
 ax.set_xticks(x,labels);ax.set_ylabel(unit);ax.set_ylim(0,ax.get_ylim()[1]*1.22);ax.legend(ncol=2,frameon=False)
 ax.set_title('Actual VM: 5 fresh sessions per configuration; mean and SD')
 ax.spines[['top','right']].set_visible(False);fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(dest/(filename+'.'+ext),dpi=170)
 plt.close(fig)
cpu=json.loads((OUT/'cpu-summary.json').read_text())['summary']
conditions=['query-1048576','kernel-1048576','copy-4096','copy-1048576','copy-16777216']
fig,axes=plt.subplots(1,2,figsize=(13,5));x=np.arange(len(conditions));width=.19
for i,(v,name,color) in enumerate(zip(variants,names,colors)):
 axes[0].bar(x+(i-1.5)*width,[cpu[v][c]['cores'] for c in conditions],width,label=name,color=color)
 axes[1].bar(x+(i-1.5)*width,[cpu[v][c]['cpu_us_iteration'] for c in conditions],width,label=name,color=color)
for ax in axes:ax.set_xticks(x,['Query','Kernel','Copy 4KiB','Copy 1MiB','Copy 16MiB'],rotation=20);ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Worker + launcher CPU cores');axes[1].set_ylabel('CPU microseconds per iteration');axes[1].set_yscale('log')
axes[0].legend(fontsize=8);fig.suptitle('Saturated sequential workload; copy iteration includes both directions')
fig.tight_layout()
for ext in ['png','svg']:fig.savefig(dest/('cpu-cost.'+ext),dpi=170)
