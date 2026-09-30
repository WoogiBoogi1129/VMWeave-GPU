"""Recompute measured outcomes from raw samples, keeping pilots separate."""
import argparse,csv,gzip,json,math,statistics
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np

def samples(path):
 with gzip.open(path,'rt') as f:return np.loadtxt(f,delimiter=',',skiprows=1,ndmin=2)
def interval(data,lo,hi):
 # Exactly count completion events; no interpolated work counters.
 mask=(data[:,1]>lo)&(data[:,1]<=hi);lat=data[mask,2]
 return {'completed':int(mask.sum()),'seconds':hi-lo,'throughput':float(mask.sum()/(hi-lo)),
   'p50_ms':float(np.percentile(lat,50)*1000) if len(lat) else None,
   'p95_ms':float(np.percentile(lat,95)*1000) if len(lat) else None,
   'p99_ms':float(np.percentile(lat,99)*1000) if len(lat) else None}
def rows_csv(path,rows):
 if not rows:return
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def process_samples(path):
 rows={}
 if not path.exists():return rows
 for line in path.read_text().splitlines():
  v=line.split()
  if len(v)<7 or line.lstrip().startswith('#') or v[3]=='-' or v[5]=='-':continue
  try:
   t=datetime.strptime(v[0]+' '+v[1],'%Y%m%d %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp()
   rows.setdefault(int(v[3]),[]).append((t,float(v[5])))
  except ValueError:continue
 return rows
def main(root):
 root=Path(root);dest=root/'analysis';dest.mkdir(exist_ok=True)
 singles=[];overhead=[];dynamic=[];failures=[];trends=[]
 proc=process_samples(root/'monitoring/pmon.txt')
 for run in sorted((root/'runs').iterdir()):
  if run.name.startswith('pilot-'):continue
  if (run/'failure.json').exists():failures.append({'run':run.name,**json.loads((run/'failure.json').read_text())});continue
  if not (run/'execution.json').exists() or not (run/'cleanup.json').exists():continue
  execution=json.loads((run/'execution.json').read_text());identity=json.loads((run/'identity.json').read_text())
  if execution['exit_code'] or any(x['status']!='PASS' for x in execution['results']):raise ValueError('invalid completed run '+run.name)
  if run.name.startswith('perf-c-'):
   timed,fixed=execution['results'];data=samples(run/(run.name+'-timed.csv.gz'));row={'run':run.name,'cap':identity['cap'],**interval(data,15,105),'fixed_completed':fixed['completed'],'fixed_seconds':fixed['elapsed_s'],'utc_start':timed['utc_start']-identity.get('clock_offset',0)}
   telemetry=run/'telemetry.json'
   if telemetry.exists():
    ts=json.loads(telemetry.read_text()).get('gpu_util',{}).get('data',{}).get('result',[])
    vals=[float(v) for s in ts if s['metric'].get('UUID')==identity['gpu_uuid'] for t,v in s['values'] if row['utc_start']+15<=float(t)<=row['utc_start']+105 and math.isfinite(float(v)) and 0<=float(v)<=100]
    row['gpu_util_mean']=statistics.mean(vals) if vals else None
    row['gpu_samples']=len(vals)
    row['enforcement']='NOT_EVALUATED' if len(vals)<86 else ('BASELINE' if row['cap']==100 else ('PASS' if row['gpu_util_mean']<=row['cap']+10 else 'FAIL'))
   else:row.update(gpu_util_mean=None,gpu_samples=0,enforcement='NOT_EVALUATED')
   singles.append(row)
   for lo in range(0,120,30):
    trend={'run':run.name,'cap':identity['cap'],'window_start_s':lo,'window_end_s':lo+30,**interval(data,lo,lo+30)}
    values=[float(v) for s in ts if s['metric'].get('UUID')==identity['gpu_uuid'] for t,v in s['values'] if row['utc_start']+lo<float(t)<=row['utc_start']+lo+30 and math.isfinite(float(v)) and 0<=float(v)<=100] if telemetry.exists() else []
    trend.update(gpu_util_mean=statistics.mean(values) if values else None,gpu_samples=len(values));trends.append(trend)
  elif run.name.startswith('perf-o-'):
   for result in execution['results']:
    mode=result['mode'];size=result['bytes'];data=samples(run/(run.name+'-'+mode+'-'+str(size)+'.csv.gz'))
    assert len(data)==result['completed']
    metrics=[('H2D',1),('D2H',2)] if mode=='copy' else [(mode,1 if mode=='query' else 2)]
    for metric,col in metrics:
     latency=data[:,col];overhead.append({'run':run.name,'path':identity['path'],'metric':metric,'bytes':size,'completed':len(data),'mean_us':float(latency.mean()*1e6),'p50_us':float(np.percentile(latency,50)*1e6),'p95_us':float(np.percentile(latency,95)*1e6),'p99_us':float(np.percentile(latency,99)*1e6),'operations_per_s':result['operations_per_s'],'effective_gib_s':size/float(latency.mean())/2**30 if mode=='copy' else None})
 for pairfile in sorted((root/'pairs').glob('*.json')) if (root/'pairs').exists() else []:
  if pairfile.name.endswith('-failure.json'):continue
  pair=json.loads(pairfile.read_text());run=root/'runs'/pair['a']
  if not (run/'execution.json').exists() or not (run/'cleanup.json').exists():continue
  data=samples(run/(run.name+'-timed.csv.gz'));stages={k:interval(data,*v) for k,v in [('solo',(15,45)),('shared',(90,150)),('recovered',(195,225))]}
  other=root/'runs'/pair['b']
  if not (other/'execution.json').exists() or not (other/'cleanup.json').exists():continue
  ar=json.loads((run/'execution.json').read_text())['results'][0];br=json.loads((other/'execution.json').read_text())['results'][0]
  ai=json.loads((run/'identity.json').read_text());bi=json.loads((other/'identity.json').read_text())
  bstart=br['utc_start']-bi.get('clock_offset',0)-(ar['utc_start']-ai.get('clock_offset',0));bend=bstart+br['elapsed_s']
  bins=np.histogram(data[:,1],bins=np.arange(0,242))[0];baseline=stages['solo']['throughput'];recovery=None;entry=None
  for t in range(math.ceil(bend),236):
   if all(abs(float(x)-baseline)<=baseline*.1 for x in bins[t:t+5]):entry=t-bend;recovery=t+5-bend;break
  entering=interval(data,bstart,bstart+10);leaving=interval(data,bend,min(bend+10,240))
  row={'pair':pair['name'],'cap_a':pair['cap_a'],'cap_b':pair['cap_b'],'slot':pair['always_active_slot'],'solo_q':baseline,'shared_q':stages['shared']['throughput'],'recovered_q':stages['recovered']['throughput'],'retention':stages['shared']['throughput']/baseline,'solo_p95_ms':stages['solo']['p95_ms'],'shared_p95_ms':stages['shared']['p95_ms'],'entry_10s_q':entering['throughput'],'entry_10s_p95_ms':entering['p95_ms'],'exit_10s_p95_ms':leaving['p95_ms'],'b_actual_start_s':bstart,'b_actual_end_s':bend,'recovery_s':recovery,'recovery_band_entry_s':entry}
  origin=ar['utc_start']-ai.get('clock_offset',0)
  for role,folder,cap in [('a',run,pair['cap_a']),('b',other,pair['cap_b'])]:
   runtime=json.loads((folder/'runtime-libraries.json').read_text());pid=next(x['pid'] for x in runtime if 'flyt-shm-worker' in x['command'])
   vals=[v for t,v in proc.get(pid,[]) if origin+90<t<=origin+150 and 0<=v<=100]
   row['pmon_util_'+role]=statistics.mean(vals) if vals else None;row['pmon_samples_'+role]=len(vals)
   ident=json.loads((folder/'identity.json').read_text())
   telemetry=json.loads((folder/'telemetry.json').read_text()) if (folder/'telemetry.json').exists() else {}
   series=[s for s in telemetry.get('hami_util',{}).get('data',{}).get('result',[]) if s['metric'].get('pod')==ident['worker'] and s['metric'].get('device_uuid')==ident['gpu_uuid']]
   if len(series)>1:raise ValueError('ambiguous worker utilization series '+folder.name)
   hvals=[float(v) for s in series for t,v in s['values'] if origin+90<float(t)<=origin+150 and math.isfinite(float(v)) and 0<=float(v)<=100]
   mean=statistics.mean(hvals) if hvals else None
   row['shared_util_'+role]=mean;row['shared_util_samples_'+role]=len(hvals)
   row['shared_cap_'+role]='NOT_EVALUATED' if len(hvals)<57 else ('PASS' if mean<=cap+10 else 'FAIL')
  dynamic.append(row)
 for name,rows in [('single',singles),('overhead',overhead),('shared',dynamic)]:rows_csv(dest/(name+'.csv'),rows)
 rows_csv(dest/'single-timecourse.csv',trends)
 summary={'single_runs':len(singles),'overhead_sessions':len({r['run'] for r in overhead}),'overhead_measurement_windows':len({(r['run'],('copy' if r['metric'] in ['H2D','D2H'] else r['metric']),r['bytes']) for r in overhead}),'overhead_metric_rows':len(overhead),'shared_pairs':len(dynamic),'failures':failures,'single':{},'overhead':{},'shared':{}}
 for cap in [25,50,75,100]:
  rs=[r for r in singles if r['cap']==cap]
  if rs:summary['single'][str(cap)]={'n':len(rs),**{k:{'mean':statistics.mean(r[k] for r in rs),'sd':statistics.stdev(r[k] for r in rs) if len(rs)>1 else 0} for k in ['throughput','p95_ms','fixed_seconds']},'gpu_util_mean':statistics.mean(r['gpu_util_mean'] for r in rs if r['gpu_util_mean'] is not None) if any(r['gpu_util_mean'] is not None for r in rs) else None,'enforcement':[r['enforcement'] for r in rs]}
 for metric,size in sorted({(r['metric'],r['bytes']) for r in overhead}):
  key=f'{metric}-{size}';summary['overhead'][key]={}
  for path in 'NTS':
   rs=[r for r in overhead if r['path']==path and r['metric']==metric and r['bytes']==size]
   if rs:summary['overhead'][key][path]={'n':len(rs),**{k:{'mean':statistics.mean(r[k] for r in rs),'sd':statistics.stdev(r[k] for r in rs) if len(rs)>1 else 0} for k in ['mean_us','operations_per_s']}}
 for ca,cb,slot in [(50,50,'a'),(50,50,'b'),(25,75,'a'),(75,25,'b')]:
  rs=[r for r in dynamic if (r['cap_a'],r['cap_b'],r['slot'])==(ca,cb,slot)]
  if rs:
   keys=['retention','solo_q','shared_q','solo_p95_ms','shared_p95_ms']
   summary['shared'][f'{ca}/{cb}/{slot}']={'n':len(rs),**{k:statistics.mean(r[k] for r in rs) for k in keys},'sd':{k:statistics.stdev(r[k] for r in rs) if len(rs)>1 else 0 for k in keys}}
 (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();main(a.root)
