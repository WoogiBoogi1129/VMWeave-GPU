from pathlib import Path
import json,csv,statistics,re,subprocess,time
O=Path('experiments/ai-passthrough/results/20261026-bulk-short');rows=[]
manifest=json.loads((O/'manifest.json').read_text())
for p in sorted((O/'formal').glob('*/*/*/result.json')):
 r=json.loads(p.read_text());assert r['correct'];assert r['binary_sha256']==manifest['binaries'][r['workload']];assert sum(x['warmup'] for x in r['samples'])==1
 for x in r['samples']:
  if not x['warmup']:rows.append({'round':p.parents[2].name,'mode':r['mode'],'workload':r['workload'],'iteration':x['iteration'],'seconds':x['seconds']})
assert len(rows)==48,len(rows)
with (O/'raw.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
stats=[]
for w in ['nw','lu','srad','sc']:
 means={m:statistics.mean(r['seconds'] for r in rows if r['workload']==w and r['mode']==m) for m in ['flyt','off','on']}
 for m in ['flyt','off','on']:
  vals=[r['seconds'] for r in rows if r['workload']==w and r['mode']==m];assert len(vals)==(1 if w=='sc' else 5)
  stats.append({'workload':w,'mode':m,'n':len(vals),'mean_s':means[m],'median_s':statistics.median(vals),'min_s':min(vals),'max_s':max(vals),'std_s':statistics.stdev(vals) if len(vals)>1 else None,'off_time_reduction_pct':100*(1-means[m]/means['off']),'flyt_time_ratio':means[m]/means['flyt'],'session_means':{rd:statistics.mean(r['seconds'] for r in rows if r['workload']==w and r['mode']==m and r['round']==rd) for rd in sorted({r['round'] for r in rows if r['workload']==w and r['mode']==m})}})
(O/'comparison.json').write_text(json.dumps(stats,indent=2)+'\n')
copy=[]
for mode in ['off','on']:
 for r in json.loads((O/'copy'/f'{mode}-copy.json').read_text()):
  assert r['correct'] and sum(x['warmup'] for x in r['samples'])==1
  vals=[x['seconds'] for x in r['samples'] if not x['warmup']];assert len(vals)==5
  copy.append({'mode':mode,'bytes':r['bytes'],'direction':r['direction'],'median_s':statistics.median(vals),'samples_s':vals})
for r in copy:
 ref=next(v for v in copy if v['mode']=='off' and v['bytes']==r['bytes'] and v['direction']==r['direction']);r['time_increase_pct']=100*(r['median_s']/ref['median_s']-1)
(O/'copy-comparison.json').write_text(json.dumps(copy,indent=2)+'\n')
diag=[]
for mode in ['off','on']:
 text=(O/'diagnostic'/f'{mode}-syscalls.log').read_text();totals={}
 for name in ['sendto','recvfrom','sendmsg','recvmsg']:
  vals=[int(x) for x in re.findall(r'\b'+name+r'\(.*?\)\s+=\s+(\d+)',text)]
  totals[name]={'calls':len(vals),'returned_bytes':sum(vals)}
 diag.append({'mode':mode,'socket_syscalls':totals,'scope':'separate diagnostic process: allocations + 16MiB H2D/D2H + explicit sync + frees; syscall returned bytes, not formal timing','fd_transfer_observed':'SCM_RIGHTS' in text})
assert diag[1]['fd_transfer_observed'],'ON feature not evidenced'
assert diag[1]['socket_syscalls']['sendto']['returned_bytes']<diag[0]['socket_syscalls']['sendto']['returned_bytes']
(O/'diagnostic-summary.json').write_text(json.dumps(diag,indent=2)+'\n')
print('PASS: 48 measured samples, 42 copy conditions x 5 samples; diagnostic FD and byte reduction verified')
