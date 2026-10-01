"""Standalone whole-system figures from independent session means."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
data=json.loads((OUT/'summary.json').read_text());assert data['complete'];s=data['summary']
out=OUT/'figures';out.mkdir(exist_ok=True)
for name,metrics,labels in [('calls',['query','kernel','longkernel'],['Query','Short launch + sync','Long launch + sync']),('copies',['h2d-4096','d2h-4096','h2d-65536','d2h-65536','h2d-1048576','d2h-1048576','h2d-4194304','d2h-4194304','h2d-16777216','d2h-16777216'],['H2D 4KiB','D2H 4KiB','H2D 64KiB','D2H 64KiB','H2D 1MiB','D2H 1MiB','H2D 4MiB','D2H 4MiB','H2D 16MiB','D2H 16MiB'])]:
 fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(metrics))
 for i,(system,label,color) in enumerate([('T','Flyt TCP/RPC + MPS','#5577aa'),('S','Improved SHM + HAMi','#c48b39')]):
  means=[s[system][m]['mean_us']/1000 for m in metrics];errors=[s[system][m]['sd_us']/1000 for m in metrics]
  bars=ax.bar(x+(i-.5)*.36,means,.36,yerr=errors,capsize=3,label=label,color=color)
  ax.bar_label(bars,labels=[f'{v:.2f}' for v in means],fontsize=8,padding=4)
 ax.set_xticks(x,labels,rotation=20 if name=='copies' else 0);ax.set_ylabel('Guest end-to-end latency (ms)');ax.set_ylim(0,ax.get_ylim()[1]*1.2)
 ax.set_title('Whole systems: five fresh sessions each; mean and SD');ax.legend(frameon=False);ax.spines[['top','right']].set_visible(False);fig.tight_layout()
 for ext in ['png','svg']:fig.savefig(out/(name+'.'+ext),dpi=170)
 plt.close(fig)
cpu=json.loads((OUT/'cpu-summary.json').read_text())['summary'];conditions=['query-1048576','kernel-1048576','longkernel-1048576','copy-4096','copy-65536','copy-1048576','copy-4194304','copy-16777216']
fig,axes=plt.subplots(1,2,figsize=(14,5));x=np.arange(len(conditions))
for i,(system,label,color) in enumerate([('T','TCP/RPC + MPS','#5577aa'),('S','SHM + HAMi','#c48b39')]):
 for ax,field in zip(axes,['cores','cpu_us_iteration']):ax.bar(x+(i-.5)*.36,[cpu[system][c][field] for c in conditions],.36,label=label,color=color)
for ax in axes:ax.set_xticks(x,['Query','Short kernel','Long kernel','4KiB','64KiB','1MiB','4MiB','16MiB'],rotation=35);ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Total accounted CPU cores');axes[1].set_ylabel('CPU microseconds / iteration');axes[1].set_yscale('log');axes[0].legend(frameon=False)
fig.suptitle('Saturated sequential workload; copy iteration includes both directions');fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/('cpu-cost.'+ext),dpi=170)
