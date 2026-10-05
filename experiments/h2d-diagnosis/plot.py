"""Publication figures generated only from recorded session-level summaries."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.size':10,'figure.dpi':140,'savefig.dpi':180})
data=json.loads((OUT/'summary.json').read_text());groups=data['groups'];figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
def select(phase,path=None,variant=None,metrics=None,mode='copy',size=16777216):
    return next(g for g in groups if g['phase']==phase and (path is None or g['path']==path) and (variant is None or g['variant']==variant) and (metrics is None or g['metrics']==metrics) and g['mode']==mode and g['bytes']==size)
def savefig(fig,name):
    fig.tight_layout();fig.savefig(figdir/(name+'.png'));fig.savefig(figdir/(name+'.svg'));plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(10,3.6))
for ax,key,title in zip(axes,['first_seconds','second_seconds'],['H2D + synchronization','D2H + synchronization']):
    for path,label,color in [('T','TCP/RPC + MPS','#c16d20'),('S','Stock SHM + HAMi','#267cb9')]:
        rows=[select('main',path=path,size=n*1048576) for n in [4,8,12,16]]
        ax.errorbar([4,8,12,16],[r[key]['mean']['mean'] for r in rows],yerr=[r[key]['mean']['sd'] for r in rows],marker='o',capsize=4,label=label,color=color)
    ax.set(xlabel='Payload (MiB)',ylabel='Latency (ms)',title=title,xticks=[4,8,12,16]);ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Five independent VM sessions; error bars = session SD',fontsize=10)
savefig(fig,'main-sweep')
fig,axes=plt.subplots(1,2,figsize=(10,3.8))
for j,(key,title) in enumerate([('first_seconds','H2D + synchronization'),('second_seconds','D2H + synchronization')]):
    ax=axes[j];x=np.arange(2)
    for off,phase,label,color in [(-.18,'cause','Metrics ON','#84b6d8'),(.18,'confirm','Metrics OFF','#267cb9')]:
        rows=[select(phase,variant=v) for v in ['original','direct']]
        ax.bar(x+off,[r[key]['mean']['mean'] for r in rows],.36,yerr=[r[key]['mean']['sd'] for r in rows],capsize=4,color=color,label=label)
    ax.set(xticks=x,xticklabels=['Original','One copy removed'],ylabel='Latency (ms)',title=title);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
fig.suptitle('16 MiB; five independent VM sessions; error bars = session SD',fontsize=10)
savefig(fig,'causal-confirmation')
fig,ax=plt.subplots(figsize=(7.5,3.6));x=np.arange(2);bottom=np.zeros(2)
for key,label,color in [('guest_pack','Guest staging','#8cbf88'),('guest_shm_write','Guest SHM write','#59a7cf'),('worker_snapshot','Worker private snapshot','#c8a3d1'),('cuda_h2d_api','CUDA H2D API','#e3aa64')]:
    vals=[next(s for s in data['stages'] if s['phase']=='cause' and s['mode']=='copy' and s['variant']==v and s['bytes']==16777216)['stages_ms'][key]['mean'] for v in ['original','direct']]
    ax.bar(x,vals,bottom=bottom,label=label,color=color);bottom+=vals
ax.set(xticks=x,xticklabels=['Original','One copy removed'],ylabel='Local interval means (ms)',title='16 MiB H2D: selected non-overlapping work intervals')
ax.legend(loc='upper right',fontsize=8);ax.grid(axis='y',alpha=.2)
fig.text(.02,.01,'Five-session means, not end-to-end: queue waits, sync and other work omitted.',fontsize=8)
fig.subplots_adjust(bottom=.16);savefig(fig,'stages')
fig,axes=plt.subplots(1,2,figsize=(9,3.5));rows=[select('main',path='T'),select('main',path='S'),select('confirm',variant='original'),select('confirm',variant='direct')]
for ax,key,title in zip(axes,['cpu_cores','cpu_us_iteration'],['CPU cores equivalent','CPU time per H2D+D2H iteration (µs)']):
    ax.bar(range(4),[r[key]['mean'] for r in rows],yerr=[r[key]['sd'] for r in rows],capsize=4,color=['#c16d20','#267cb9','#84b6d8','#3b9765']);ax.set(xticks=range(4),xticklabels=['TCP','Stock SHM','Control OFF','Direct OFF'],title=title);ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.2)
fig.suptitle('16 MiB roundtrip; five independent VM sessions; error bars = session SD',fontsize=10)
savefig(fig,'cpu-cost')
