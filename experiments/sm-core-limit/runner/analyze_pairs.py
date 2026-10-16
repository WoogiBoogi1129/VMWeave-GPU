"""Offline analysis of matched Worker identities, raw metrics and release evidence."""
import json,statistics,datetime,math
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/sm-core-limit/evidence/pairs-20261016'
rows=[json.loads(l) for l in (OUT/'monitor.jsonl').read_text().splitlines()]
pm=[]
for line in (OUT/'pmon.txt').read_text().splitlines():
 x=line.split()
 if len(x)<7 or not x[0].isdigit() or not x[3].isdigit() :continue
 t=datetime.datetime.strptime(x[0]+' '+x[1],'%Y%m%d %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Seoul')).timestamp()
 pm.append({'utc':t,'pid':int(x[3]),'sm':float(x[5]) if x[5].isdigit() else None})
summary=[]
for d in sorted(OUT.glob('pair-*')):
 if not (d/'result.json').exists():continue
 result=json.loads((d/'result.json').read_text());cfg=result['protocol'];start=cfg['start_utc'];end=start+178
 valid=[r for r in rows if start+35<=r['utc']<end and 'gpu_util' in r]
 assert len(valid)>50,(d,len(valid))
 pair={'pair':d.name,'start_utc':start,'samples':len(valid),'device_util_mean':statistics.mean(r['gpu_util'] for r in valid),'workers':[],'series':[]}
 for i,slot in enumerate('ab'):
  worker=cfg['workers'][i];pid=cfg['host_pids'][i];cap=cfg['caps'][i];path=d/slot
  ident=json.loads((path/'identity.json').read_text());lib=json.loads((path/'library-mount.json').read_text());proc=json.loads((path/'host-process.json').read_text());release=json.loads((path/'channel-released.json').read_text())
  assert lib['sha256']=='f30f08c8f4bbdada1856231f2ec269d50fc81e08881a4146c9c1bbb3173aebd8'
  assert ident['gpu_uuid']==cfg['gpu_uuid'] and ident['worker_uid']==lib['pod_uid']
  assert proc['pid']==pid and int(proc['env']['CUDA_DEVICE_SM_LIMIT'])==cap and proc['env']['GPU_CORE_UTILIZATION_POLICY']=='FORCE'
  assert release['metadata']['uid']==ident['channel_uid'] and release['status']['phase']=='Released'
  assert result['returncodes'][i]==0
  assert result['results'][i]['launches']>0 and result['results'][i]['seconds']>148
  assert math.isfinite(result['results'][i]['sample']) and abs(result['results'][i]['sample']-1114.480103)<0.001
  vals=[];tail_vals=[];series=[]
  for r in rows:
   if not start-5<=r['utc']<start+185:continue
   for l in r.get('hami','').splitlines():
    if l.startswith('hami_container_device_utilization_ratio{') and f'pod="{worker}"' in l:
     v=float(l.rsplit(' ',1)[1]);series.append([r['utc']-start,v])
     if start+35<=r['utc']<end:vals.append(v)
     if start+120<=r['utc']<end:tail_vals.append(v)
  assert len(vals)>50,(worker,len(vals))
  process_rows=[r for r in pm if r['pid']==pid and start+35<=r['utc']<end]
  pvals=[r['sm'] for r in process_rows if r['sm'] is not None]
  assert len(pvals)>20,(worker,len(pvals))
  events=[json.loads(l) for l in (path/'events.jsonl').read_text().splitlines()]
  ready=next(r for r in events if r['event']=='ready');measurement=next(r for r in events if r['event']=='measurement_start')
  assert ready['received_utc']<start
  pair['workers'].append({'slot':slot,'cap':cap,'pod':worker,'host_pid':pid,'hami_util_mean':statistics.mean(vals),'hami_samples':len(vals),'hami_above_cap_fraction':sum(v>cap for v in vals)/len(vals),'last_minute_hami_util_mean':statistics.mean(tail_vals),'pmon_util_mean':statistics.mean(pvals),'pmon_samples':len(pvals),'pmon_missing_samples':len(process_rows)-len(pvals),'pmon_numeric_coverage':len(pvals)/len(process_rows),'launches_per_second':result['results'][i]['launches_per_second'],'measurement_start_received_utc':measurement['received_utc'],'released':True,'library_sha256':lib['sha256']})
  pair['series'].append({'slot':slot,'cap':cap,'samples':series})
 total=sum(w['launches_per_second'] for w in pair['workers'])
 for w in pair['workers']:w['throughput_share_pct']=100*w['launches_per_second']/total
 pair['measurement_start_receipt_skew_ms']=1000*abs(pair['workers'][0]['measurement_start_received_utc']-pair['workers'][1]['measurement_start_received_utc'])
 seen={r['pid'] for r in pm if start+35<=r['utc']<end}
 assert seen==set(cfg['host_pids']),(d,seen,cfg['host_pids'])
 pair['total_launches_per_second']=total;summary.append(pair)
assert len(summary)==3,len(summary)
aggregate=[]
for cap in [25,75]:
 ws=[w for p in summary for w in p['workers'] if w['cap']==cap]
 r={'cap':cap,'runs':len(ws)}
 for k in ['hami_util_mean','pmon_util_mean','launches_per_second','throughput_share_pct']:
  vs=[w[k] for w in ws];r[k]=statistics.mean(vs);r[k+'_sd']=statistics.stdev(vs)
 aggregate.append(r)
output={'pairs':summary,'aggregate':aggregate,'gpu_uuid':cfg['gpu_uuid'],'all_six_released':True,'collector_errors':sum('error' in r for r in rows),'scope':'3 independent pairs; averages across run means, not independent one-second samples'}
(OUT/'summary.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({'aggregate':aggregate,'all_six_released':True},indent=2))
