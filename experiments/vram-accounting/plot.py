"""Publication plots from audited measurements, not synthetic curves."""
import json,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;E=P/'evidence/20261016';s=json.loads((E/'summary.json').read_text());M=1048576
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
def save(fig,name):
 fig.tight_layout();fig.savefig(E/(name+'.png'),dpi=180);fig.savefig(E/(name+'.pdf'));plt.close(fig)
fig,ax=plt.subplots(figsize=(9,5))
for i,q in enumerate([1024,4096]):
 rows=[r for r in s['singles'] if r['quota_mib']==q]
 if not rows:continue
 base=sum(r['baseline_bytes'] for r in rows)/len(rows)/M;usable=sum(r['warm_max'] for r in rows)/len(rows)/M
 ax.bar(i,base,color='#da9563',label='Initial accounted memory' if i==0 else None);ax.bar(i,usable,bottom=base,color='#287aa3',label='Application-allocatable memory' if i==0 else None)
 ax.text(i,base/2,f'{base:g} MiB',ha='center',va='center');ax.text(i,base+usable/2,f'{usable:g} MiB\n{usable/q*100:.2f}% · n={len(rows)}',ha='center',va='center',color='white');ax.text(i,q+90,'next 4 KiB: OOM',ha='center')
ax.set_xticks([0,1],['1 GiB quota','4 GiB quota']);ax.set_ylabel('Memory (MiB)');ax.set_ylim(0,4700);ax.set_title('VRAM quota: initial accounting and usable capacity');ax.legend(loc='upper left');save(fig,'capacity-boundary')
rows=list(csv.DictReader((E/'ledger.csv').open()));r=[x for x in rows if x['run']=='vram-single-r1-1024' and x['label']=='rounding']
fig,ax=plt.subplots(figsize=(9,4));x=list(range(len(r)));ax.bar([i-.2 for i in x],[int(v['requested']) for v in r],width=.4,label='Application request');ax.bar([i+.2 for i in x],[int(v['rounded_derived']) for v in r],width=.4,label='4 KiB rounded charge');ax.set_xticks(x,[v['requested'] for v in r],rotation=30);ax.set_yscale('log');ax.set_ylabel('Bytes (log scale)');ax.set_xlabel('Requested bytes per allocation');ax.set_title('Small allocations consume rounded quota');ax.legend();save(fig,'rounding')
if s['torch']:
 fig,axs=plt.subplots(1,2,figsize=(13,5),sharey=True)
 for ax,q in zip(axs,[1024,4096]):
  runs=[r for r in s['torch'] if r['quota_mib']==q]
  if not runs:continue
  row=runs[0]['stages'];x=list(range(len(row)))
  for key,label,style in [('allocated','Tensor allocated','o-'),('reserved','Allocator reserved','s-'),('hami_bytes','HAMi accounted','^-'),('nvml_process_bytes','NVML process','x--')]:ax.plot(x,[r[key]/M for r in row],style,label=label)
  ax.set_xticks(x,[r['stage'].replace('-','\n') for r in row],fontsize=8);ax.set_title(f'{q} MiB quota (first repetition)');ax.grid(alpha=.2);ax.set_ylabel('Memory (MiB)')
 axs[1].legend();fig.suptitle('PyTorch allocator metrics do not include all GPU process memory');save(fig,'pytorch-accounting')
print('Plots saved',E)
if s['pairs']:
 fig,ax=plt.subplots(figsize=(10,4))
 for quota,color in [(1024,'#287aa3'),(4096,'#d08540')]:
  xs=[];ys=[]
  for i,p in enumerate(s['pairs']):
   for j,r in enumerate(p['rows']):
    if r['result']['total']==quota*M:xs.append(i+1+(j-1.5)*.06);ys.append(r['size']/M)
  ax.scatter(xs,ys,color=color,label=f'{quota} MiB quota; both allocation orders')
 ax.set_xticks(range(1,len(s['pairs'])+1),[p['run'].replace('vram-pair-','') for p in s['pairs']],rotation=30);ax.set_ylabel('Successful retained allocation (MiB)');ax.set_title('Two VMs retain their usable memory on the same GPU');ax.legend();ax.grid(alpha=.2);save(fig,'pair-capacity')

if s.get('supplementary_trained_boundary'):
 fig,ax=plt.subplots(figsize=(9,5))
 for i,r in enumerate(s['supplementary_trained_boundary']):
  row=next(v for v in r['stages'] if v['stage']=='trained-max');q=r['quota_mib']
  ax.bar(i-.18,row['hami_bytes']/M,width=.36,color='#287aa3',label='HAMi accounted' if i==0 else None)
  ax.bar(i+.18,row['nvml_process_bytes']/M,width=.36,color='#d08540',label='NVML Worker' if i==0 else None)
  ax.hlines(q,i-.42,i+.42,color='black',linestyle='--',label='Configured quota' if i==0 else None)
  ax.text(i+.18,row['nvml_process_bytes']/M+80,f"{row['nvml_process_bytes']/M:g} MiB",ha='center')
 ax.set_xticks(range(len(s['supplementary_trained_boundary'])),[str(r['quota_mib'])+' MiB quota' for r in s['supplementary_trained_boundary']]);ax.set_ylabel('Memory (MiB)');ax.set_ylim(0,4700);ax.set_title('Post-training direct allocation to the logical quota boundary (n=1 each)');ax.legend(loc='upper left');save(fig,'trained-boundary')
