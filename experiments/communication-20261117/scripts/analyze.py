"""Independent block-level estimates; never treat individual calls as repeats."""
import argparse,json,gzip,csv,math,hashlib
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
T95=2.7764451051977987

def ci(values,log=False):
 a=np.asarray(values,dtype=float)
 if len(a)!=5 or np.any(~np.isfinite(a)):return None
 if log:a=np.log(a)
 mean=a.mean();h=T95*a.std(ddof=1)/math.sqrt(5)
 return [float(x) for x in (np.exp([mean,mean-h,mean+h]) if log else [mean,mean-h,mean+h])]
def writecsv(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analyze():
 rows=[];errors=[]
 for session in sorted((P/'results').glob('b[1-5]-[NVFL]')):
  e=json.loads((session/'execution.json').read_text());b=int(session.name[1]);mode=session.name[-1]
  if e.get('status')!='passed':errors.append(session.name+' failed');continue
  observations=[json.loads(l) for l in (session/'observer.jsonl').read_text().splitlines()]
  ident=json.loads((P/'evidence'/(session.name+'-session.json')).read_text())
  offset=0
  if mode!='N':
   c=min(ident['clocks'],key=lambda x:x['host_after_ns']-x['host_before_ns']);offset=c['guest_ns']-(c['host_before_ns']+c['host_after_ns'])/2
  for result in e['results']:
   id=result['id'];raw=session/f'c{id:02d}.u64.gz'
   with gzip.open(raw,'rb') as f:a=np.frombuffer(f.read(),dtype='<u8')
   assert len(a)==result['completed'] and len(a)>0 and np.all(a>0),(session,id)
   assert result['correctness']=='PASS' and result['elapsed_ns']>=30e9
   assert int(a.sum())<=result['elapsed_ns']
   elapsed=result['elapsed_ns']/1e9
   row={'block':b,'mode':mode,'id':id,'direction':result['direction'],'bytes':result['bytes'],'K':result['K'],'samples':len(a),'elapsed_s':elapsed,'p50_us':float(np.quantile(a,.5)/1000),'p95_us':float(np.quantile(a,.95)/1000) if len(a)>=1000 else None,'mean_us':float(a.mean()/1000),'GiB_s':result['bytes']*len(a)/elapsed/2**30 if result['direction']!='kernel' else None,'kernels_s':result['K']*len(a)/elapsed if result['direction']=='kernel' else None,'amortized_us':elapsed*1e6/(len(a)*result['K']) if result['K'] else None,'client_cpu_s':result['client_cpu_ns']/1e9,'path_cpu_s':None,'cpu_core_s_per_operation':None,'cpu_core_s_per_GiB':None,'cpu_throttled_s':None}
   # Interpolate cumulative counters at the observed measurement boundaries.
   begin=result['start_utc_ns']-offset;end=result['end_utc_ns']-offset
   usable=[x for x in observations if x['cpu']]
   if usable and usable[0]['utc_ns']<=begin and usable[-1]['utc_ns']>=end:
    times=np.asarray([x['utc_ns'] for x in usable],dtype=float)
    labels=['server'] if mode=='N' else ['server','qemu']
    if all(all(label in x['cpu'] for label in labels) for x in usable):
     vals=[sum(x['cpu'][label]['usage_usec'] for label in labels) for x in usable]
     delta=(np.interp(end,times,vals)-np.interp(begin,times,vals))/1e6
     th=[sum(x['cpu'][label].get('throttled_usec',0) for label in labels) for x in usable]
     row['path_cpu_s']=float(delta);row['cpu_throttled_s']=float((np.interp(end,times,th)-np.interp(begin,times,th))/1e6)
     row['cpu_core_s_per_operation']=float(delta/(len(a)*(result['K'] or 1)))
     if result['direction']!='kernel':row['cpu_core_s_per_GiB']=float(delta/(result['bytes']*len(a)/2**30))
   rows.append(row)
 if not rows:return
 dest=P/'analysis';dest.mkdir(exist_ok=True);writecsv(dest/'blocks.csv',rows)
 grouped=[]
 for mode in 'NVFL':
  for id in range(16):
   r=sorted([x for x in rows if x['mode']==mode and x['id']==id],key=lambda x:x['block'])
   if len(r)!=5:continue
   g={'mode':mode,'id':id,'direction':r[0]['direction'],'bytes':r[0]['bytes'],'K':r[0]['K'],'p95_available_blocks':sum(x['p95_us'] is not None for x in r),'min_samples':min(x['samples'] for x in r)}
   for field in ['p50_us','p95_us','GiB_s','kernels_s','amortized_us','path_cpu_s']:
    vals=[x[field] for x in r];c=ci(vals) if all(v is not None for v in vals) else None
    for name,v in zip(['mean','low95','high95'],c or [None]*3):g[field+'_'+name]=v
   grouped.append(g)
 if grouped:writecsv(dest/'summary.csv',grouped)
 comparisons=[]
 lookup={(x['block'],x['mode'],x['id']):x for x in rows}
 for id in range(16):
  for den in 'FLN':
   if not all((b,m,id) in lookup for b in range(1,6) for m in ['V',den]):continue
   for metric in ['p50_us','GiB_s','kernels_s']:
    values=[(lookup[b,'V',id][metric],lookup[b,den,id][metric]) for b in range(1,6)]
    if any(a is None or d is None for a,d in values):continue
    c=ci([a/d for a,d in values],log=True)
    comparisons.append({'id':id,'comparison':'V/'+den,'metric':metric,'ratio':c[0],'low95':c[1],'high95':c[2]})
 if comparisons:writecsv(dest/'paired-ratios.csv',comparisons)
 native=[]
 for id in range(16):
  for m in 'VFL':
   if not all((b,q,id) in lookup for b in range(1,6) for q in [m,'N']):continue
   d=ci([lookup[b,m,id]['p50_us']-lookup[b,'N',id]['p50_us'] for b in range(1,6)])
   a={'id':id,'mode':m,'p50_added_us':d[0],'low95':d[1],'high95':d[2],'bandwidth_retention_ratio':None,'bandwidth_low95':None,'bandwidth_high95':None}
   if id in range(1,13):
    q=ci([lookup[b,m,id]['GiB_s']/lookup[b,'N',id]['GiB_s'] for b in range(1,6)],log=True)
    a.update(bandwidth_retention_ratio=q[0],bandwidth_low95=q[1],bandwidth_high95=q[2])
   native.append(a)
 if native:writecsv(dest/'native-deltas.csv',native)
 validation={'valid_intervals':len(rows),'expected_intervals':320,'complete':len(rows)==320 and not errors,'errors':errors,'blocks':sorted(set(x['block'] for x in rows)),'ci':'t interval across 5 independent block values, df=4; paired ratios on log scale','quantiles':'NumPy linear interpolation, computed separately per session','cpu':'1-second cumulative disjoint Pod cgroups interpolated at clock-aligned boundaries; missing bracketing samples => N/A; excludes shared daemons and IRQ outside cgroups'}
 (dest/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
 print(json.dumps(validation,indent=2))
 if len(grouped)==64:plot(grouped,dest)
def plot(rows,dest):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 colors={'N':'#64748b','V':'#2563eb','F':'#d97706','L':'#059669'}
 labels={'N':'Native + HAMi-core','V':'VMWeave SHM','F':'Flyt TCP + MPS','L':'Lupine TCP'}
 fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
 for ax,direction in zip(axs,['H2D','D2H']):
  for m in 'NVFL':
   r=sorted([x for x in rows if x['mode']==m and x['direction']==direction],key=lambda x:x['bytes'])
   ax.plot([x['bytes'] for x in r],[x['GiB_s_mean'] for x in r],marker='o',label=labels[m],color=colors[m]);ax.fill_between([x['bytes'] for x in r],[max(0,x['GiB_s_low95']) for x in r],[x['GiB_s_high95'] for x in r],alpha=.12,color=colors[m])
  ax.set_xscale('log',base=2);ax.set_xticks([4,4096,65536,1048576,16777216,67108864],['4 B','4 KiB','64 KiB','1 MiB','16 MiB','64 MiB'],rotation=30);ax.set_title(direction);ax.set_ylabel('Completed payload / elapsed time (GiB/s)');ax.grid(alpha=.2)
 axs[1].legend(fontsize=8);fig.savefig(dest/'transfer-bandwidth.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
 for ax,direction in zip(axs,['H2D','D2H']):
  for m in 'NVFL':
   r=sorted([x for x in rows if x['mode']==m and x['direction']==direction],key=lambda x:x['bytes'])
   ax.plot([x['bytes'] for x in r],[x['p50_us_mean'] for x in r],marker='o',label=labels[m],color=colors[m])
  ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_xticks([4,4096,65536,1048576,16777216,67108864],['4 B','4 KiB','64 KiB','1 MiB','16 MiB','64 MiB'],rotation=30);ax.set_title(direction);ax.set_ylabel('Mean of block p50 completion latency (µs)');ax.grid(alpha=.2)
 axs[1].legend(fontsize=8);fig.savefig(dest/'transfer-latency.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
 for j,m in enumerate('NVFL'):
  r=next(x for x in rows if x['mode']==m and x['id']==0)
  axs[0].bar(j,r['p50_us_mean'],color=colors[m],yerr=[[r['p50_us_mean']-r['p50_us_low95']],[r['p50_us_high95']-r['p50_us_mean']]],capsize=4)
  r=sorted([x for x in rows if x['mode']==m and x['direction']=='kernel'],key=lambda x:x['K'])
  axs[1].plot([x['K'] for x in r],[x['kernels_s_mean'] for x in r],marker='o',color=colors[m],label=labels[m])
 axs[0].set_xticks(range(4),list('NVFL'));axs[0].set_ylabel('Mean of block p50 completion latency (µs)');axs[0].set_title('One kernel + synchronization');axs[1].set_xscale('log');axs[1].set_yscale('log');axs[1].set_xlabel('K launches per synchronization');axs[1].set_ylabel('Completed kernels/s');axs[1].legend(fontsize=8)
 fig.savefig(dest/'kernel-path.png',dpi=180);plt.close(fig)
if __name__=='__main__':analyze()
