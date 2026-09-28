"""Recompute statistics, correctness and extension decisions from raw samples."""
import argparse,csv,gzip,hashlib,json,statistics
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--cpu',type=Path);p.add_argument('--plots',action='store_true');a=p.parse_args();o=a.output
cpu=[]
if a.cpu and a.cpu.exists():
 for line in a.cpu.read_text().splitlines():
  row=json.loads(line)
  if row.get('pods'):cpu.append(row)
rows=[];validation=[];allwindows=[]
for run in sorted(o.glob('r*-*')):
 if not (run/'execution.json').exists() or not list(run.glob('*.csv.gz')):continue
 execution=json.loads((run/'execution.json').read_text());path=run.name.split('-')[1];rep=int(run.name.split('-')[0][1:]);offset=0
 if (run/'clock-map.json').exists():offset=min(json.loads((run/'clock-map.json').read_text()),key=lambda x:x['uncertainty'])['offset']
 events=[]
 for line in (run/'stdout.txt').read_text().splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
 for result in execution['results']:
  mode=result['mode'];size=result['bytes'];prefix=f'{run.name}-{mode}-{size}'
  data=np.loadtxt(run/(prefix+'.csv.gz'),delimiter=',',skiprows=1,usecols=(1,2),ndmin=2)
  binary=run/(prefix+'.output.bin');got=np.frombuffer(binary.read_bytes(),dtype='<u4');expected=np.arange(size//4,dtype=np.uint32)+2026
  if mode in ['kernel','resident','transfer']:expected+=19*(1 if mode=='kernel' else 64)
  mismatch=int(np.count_nonzero(got!=expected));n=len(data)
  valid=execution['exit_code']==0 and n==result['completed'] and mismatch==0 and result['mismatches']==0 and result['status']=='PASS' and np.isfinite(data).all() and (data>=0).all()
  validation.append({'session':run.name,'mode':mode,'bytes':size,'samples':n,'checked_elements':len(got),'mismatches':mismatch,'output_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'valid':bool(valid)})
  i=next(i for i,e in enumerate(events) if e.get('event')=='CONDITION' and e['mode']==mode and e['bytes']==size)
  following=events[i+1:];start=next(e for e in following if e['event']=='MEASUREMENT_START')['utc']-offset;end=next(e for e in following if e['event']=='MEASUREMENT_END')['utc']-offset
  window={'session':run.name,'path':path,'rep':rep,'mode':mode,'bytes':size,'start_host_utc':start,'end_host_utc':end,'completed':n,'elapsed_s':result['elapsed_s'],'operations_per_s':result['operations_per_s'],'cpu_core_seconds':None}
  matched=[r for r in cpu if r.get('session')==run.name];roles={p['role'] for r in matched for p in r['pods']};total=0;good=bool(roles)
  for role in roles:
   points=[(r['utc'],p['usage_usec']/1e6) for r in matched for p in r['pods'] if p['role']==role];t=np.array([p[0] for p in points]);v=np.array([p[1] for p in points]);
   if not len(t) or t.min()>start or t.max()<end:good=False;continue
   if np.max(np.diff(t[(t>=start-2)&(t<=end+2)]),initial=0)>3:good=False
   total+=float(np.interp(end,t,v)-np.interp(start,t,v))
  if good:window['cpu_core_seconds']=total;window['cpu_seconds_per_operation']=total/n
  allwindows.append(window)
  metrics=[('query_return',0)] if mode=='query' else [('launch_return',0),('launch_sync_complete',1)] if mode=='kernel' else [('h2d_complete',0),('d2h_complete',1)] if mode=='copy' else []
  for metric,col in metrics:
   values=data[:,col]*1e6
   row={'session':run.name,'path':path,'rep':rep,'mode':mode,'bytes':size,'metric':metric,'samples':n,'mean_us':float(values.mean()),'median_us':float(np.median(values)),'p95_us':float(np.quantile(values,.95)),'p99_us':float(np.quantile(values,.99)) if n>=1000 else None,'p99_status':'reported' if n>=1000 else 'insufficient_samples','effective_mib_s':size/(1024**2)/(float(values.mean())/1e6) if mode=='copy' else None};rows.append(row)
  del data

def writecsv(path,rows):
 if not rows:return
 with path.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
writecsv(o/'latency-summary.csv',rows);writecsv(o/'window-summary.csv',allwindows)
(o/'validation.json').write_text(json.dumps({'status':'PASS' if validation and all(r['valid'] for r in validation) else 'FAIL','windows':len(validation),'details':validation},indent=2)+'\n')
aggregates=[];extension=set();why=[];condition_bit={('query',1048576):0,('kernel',1048576):1,('copy',4096):2,('copy',262144):3,('copy',4194304):4,('resident',2097152):5,('transfer',2097152):6}
series=rows+[dict(w,metric='throughput',mean_us=w['operations_per_s']) for w in allwindows if w['mode'] in ['resident','transfer']]
keys=sorted({(r['mode'],r['bytes'],r['metric']) for r in series})
for mode,size,metric in keys:
 for path in 'NTS':
  rr=[r for r in series if (r['mode'],r['bytes'],r['metric'],r['path'])==(mode,size,metric,path)];v=[r['mean_us'] for r in rr]
  if not v:continue
  mean=statistics.mean(v);sd=statistics.stdev(v) if len(v)>1 else 0;cv=sd/mean
  aggregates.append({'mode':mode,'bytes':size,'metric':metric,'path':path,'n_sessions':len(v),'mean':mean,'sample_sd':sd,'cv':cv,'min':min(v),'max':max(v),'unit':'operations/s' if metric=='throughput' else 'us'})
  first=[r['mean_us'] for r in rr if r['rep']<=3]
  if len(first)==3 and statistics.stdev(first)/statistics.mean(first)>.1:extension.add(condition_bit[(mode,size)]);why.append({'mode':mode,'bytes':size,'metric':metric,'path':path,'reason':'first-three run-mean CV > 10%'})
 for p1,p2 in [('N','T'),('N','S'),('T','S')]:
  signs=[]
  for rep in [1,2,3]:
   a1=[r['mean_us'] for r in series if (r['mode'],r['bytes'],r['metric'],r['path'],r['rep'])==(mode,size,metric,p1,rep)];a2=[r['mean_us'] for r in series if (r['mode'],r['bytes'],r['metric'],r['path'],r['rep'])==(mode,size,metric,p2,rep)]
   if a1 and a2:signs.append(np.sign(a1[0]-a2[0]))
  if len(signs)==3 and min(signs)<0<max(signs):extension.add(condition_bit[(mode,size)]);why.append({'mode':mode,'bytes':size,'metric':metric,'pair':p1+p2,'reason':'first-three paired ordering reverses'})
writecsv(o/'aggregate-summary.csv',aggregates)
(o/'extension-decision.json').write_text(json.dumps({'first_three_complete':sum(1 for w in allwindows if w['rep']<=3)==63,'condition_mask':sum(1<<b for b in extension),'reasons':why,'rule':'Extend all N/T/S affected conditions to six fresh sessions; no dropping valid original runs.'},indent=2)+'\n')
print(json.dumps({'windows':len(validation),'valid':all(r['valid'] for r in validation),'extension_mask':sum(1<<b for b in extension),'cpu_windows':sum(w['cpu_core_seconds'] is not None for w in allwindows)}))
if a.plots:
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plots=o/'plots';plots.mkdir(exist_ok=True);colors={'N':'#495867','T':'#ce6a36','S':'#2b8c8f'}
 for metric in ['query_return','launch_return','launch_sync_complete','h2d_complete','d2h_complete','throughput']:
  subset=[r for r in aggregates if r['metric']==metric]
  if not subset:continue
  labels=sorted({(r['mode'],r['bytes']) for r in subset});fig,ax=plt.subplots(figsize=(8,4.5));x=np.arange(len(labels))
  for j,path in enumerate('NTS'):
   vals=[next((r for r in subset if r['path']==path and (r['mode'],r['bytes'])==label),None) for label in labels]
   mean=[v['mean'] if v else np.nan for v in vals];err=[v['sample_sd'] if v else 0 for v in vals];pos=x+(j-1)*.24
   ax.bar(pos,mean,.22,yerr=err,capsize=4,label=path,color=colors[path],alpha=.75)
   for at,label in zip(pos,labels):
    points=[r['mean_us'] for r in series if r['path']==path and r['metric']==metric and (r['mode'],r['bytes'])==label];ax.scatter([at]*len(points),points,color='black',s=15,zorder=5)
  ax.set_xticks(x,[mode if metric=='throughput' else f'{size/1024:g} KiB' for mode,size in labels]);ax.set_ylabel('Completed operations / s' if metric=='throughput' else 'Latency (microseconds; log scale)');
  if metric!='throughput':ax.set_yscale('log')
  ax.set_title(metric.replace('_',' ')+' — independent session means');ax.legend(title='N: native+HAMi / T: TCP+MPS / S: SHM+HAMi',fontsize=8);ax.grid(axis='y',alpha=.25);fig.tight_layout()
  for ext in ['png','svg']:fig.savefig(plots/(metric+'.'+ext),dpi=180)
  plt.close(fig)
