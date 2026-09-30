"""Publication figures derived only from exported original measurements."""
import csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import samples
root=Path(sys.argv[1]);out=root/'figures';out.mkdir(exist_ok=True)
summary=json.loads((root/'analysis/summary.json').read_text())
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
def finish(fig,name):
 fig.tight_layout();fig.savefig(out/(name+'.png'));fig.savefig(out/(name+'.svg'));plt.close(fig)
if summary['single']:
 caps=[int(k) for k in summary['single']];rs=[summary['single'][str(c)] for c in caps]
 fig,ax=plt.subplots(1,3,figsize=(14,4))
 ax[0].plot(caps,[r['gpu_util_mean'] for r in rs],'o-',label='Observed mean')
 ax[0].plot(caps,caps,'--',color='gray',label='Requested upper limit')
 ax[0].set(xlabel='HAMi compute cap (%)',ylabel='Whole-GPU utilization (%)',ylim=(0,110),title='Single VM: upper-limit behavior');ax[0].legend(fontsize=8)
 for a,key,title,unit in [(ax[1],'throughput','Completed work','jobs/s'),(ax[2],'fixed_seconds','Fixed 2,500 jobs','seconds')]:
  a.errorbar(caps,[r[key]['mean'] for r in rs],yerr=[r[key]['sd'] for r in rs],fmt='o-',capsize=4)
  a.set(xlabel='HAMi compute cap (%)',ylabel=unit,title=title+' (mean ± SD)');a.grid(alpha=.2)
 finish(fig,'single-caps')
if summary['overhead']:
 keys=[k for k in summary['overhead'] if not k.startswith(('resident','transfer'))]
 fig,ax=plt.subplots(figsize=(14,5));x=np.arange(len(keys));colors=['#475569','#0f766e','#7c3aed']
 for j,p in enumerate('NTS'):
  vals=[summary['overhead'][k].get(p,{}) for k in keys]
  ax.bar(x+(j-1)*.25,[v.get('mean_us',{}).get('mean',np.nan) for v in vals],.25,label=p,color=colors[j],yerr=[v.get('mean_us',{}).get('sd',0) for v in vals],capsize=2)
 ax.set(yscale='log',ylabel='Latency (µs, log scale)',title='Full path latency: independent-session mean ± SD',xticks=x,xticklabels=[k.replace('-','\n',1) for k in keys]);ax.legend();ax.grid(axis='y',alpha=.2)
 finish(fig,'path-latency')
 fig,ax=plt.subplots(figsize=(8,4));keys=[k for k in summary['overhead'] if k.startswith(('resident','transfer'))];x=np.arange(len(keys))
 for j,p in enumerate('NTS'):
  vals=[summary['overhead'][k].get(p,{}) for k in keys]
  ax.bar(x+(j-1)*.25,[v.get('operations_per_s',{}).get('mean',np.nan) for v in vals],.25,label=p,color=colors[j],yerr=[v.get('operations_per_s',{}).get('sd',0) for v in vals],capsize=3)
 ax.set(yscale='log',ylabel='Completed jobs/s (log scale)',title='Throughput: independent-session mean ± SD',xticks=x,xticklabels=['Resident data','Transfer-inclusive']);ax.legend();ax.grid(axis='y',alpha=.2)
 finish(fig,'path-throughput')
for pairfile in sorted((root/'pairs').glob('*r1-*-a.json')) if (root/'pairs').exists() else []:
 p=json.loads(pairfile.read_text());ra=root/'runs'/p['a'];rb=root/'runs'/p['b']
 if not (ra/'cleanup.json').exists() or not (rb/'cleanup.json').exists():continue
 ar=json.loads((ra/'execution.json').read_text())['results'][0];ai=json.loads((ra/'identity.json').read_text());origin=ar['utc_start']-ai.get('clock_offset',0)
 fig,ax=plt.subplots(3,1,figsize=(12,9),sharex=True)
 for run,label,color in [(ra,'A (continuous)','#7c3aed'),(rb,'B (starts/stops)','#0f766e')]:
  r=json.loads((run/'execution.json').read_text())['results'][0];ident=json.loads((run/'identity.json').read_text());offset=r['utc_start']-ident.get('clock_offset',0)-origin
  data=samples(run/(run.name+'-timed.csv.gz'));times=data[:,1]+offset;bins=np.arange(0,242);count=np.histogram(times,bins=bins)[0]
  active=(bins[:-1]>=offset)&(bins[:-1]<offset+r['elapsed_s'])
  ax[0].plot(bins[:-1][active],count[active],color=color,alpha=.25)
  smooth=np.convolve(count,np.ones(5)/5,mode='same');ax[0].plot(bins[:-1][active],smooth[active],color=color,label=label+' (5 s mean)')
  points=[]
  for t in range(240):
   lat=data[(times>=t)&(times<t+1),2]
   if len(lat)>=20:points.append((t,np.percentile(lat,95)*1000))
  if points:ax[1].plot(*np.array(points).T,color=color,label=label)
 telemetry=ra/'telemetry.json'
 if telemetry.exists():
  ts=json.loads(telemetry.read_text())['gpu_util']['data']['result']
  for row in ts:ax[2].plot([float(t)-origin for t,v in row['values']],[float(v) for t,v in row['values']],color='#475569')
 for a in ax:
  a.axvline(60,color='gray',linestyle='--');a.axvline(180,color='gray',linestyle='--');a.grid(alpha=.2);a.set_xlim(0,240)
 ax[0].set(ylabel='Completed jobs/s',title=f"Two VMs, caps {p['cap_a']}/{p['cap_b']}, repetition 1");ax[0].legend()
 ax[1].set(ylabel='Per-second p95 latency (ms)');ax[1].legend()
 ax[2].set(ylabel='Whole-GPU utilization (%)',xlabel='Seconds from A measurement start',ylim=(0,110))
 finish(fig,'shared-'+str(p['cap_a'])+'-'+str(p['cap_b']))
