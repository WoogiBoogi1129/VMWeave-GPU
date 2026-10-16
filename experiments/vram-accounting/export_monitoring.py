"""Export observed monitoring data and exact queries; no reconstructed metric values."""
import json,lzma,urllib.parse,urllib.request,csv
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];B=ROOT/'.local/vram-accounting-20261016';E=P/'evidence/20261016/monitoring';E.mkdir(parents=True,exist_ok=True)
rows=[]
with (B/'monitor.jsonl').open() as f:
 for line in f:
  try:r=json.loads(line)
  except json.JSONDecodeError:continue
  if 'gpu_mib' in r:rows.append(r)
assert rows;start=rows[0]['utc'];end=rows[-1]['utc']
# Remove unrelated persistent Worker labels from the shared-GPU exporter response.
with lzma.open(E/'observations.jsonl.xz','wt') as f:
 for r in rows:
  r['hami']='\n'.join(l for l in r['hami'].splitlines() if 'pod="vram-' in l);f.write(json.dumps(r)+'\n')
queries={'device':'vram_device_used_bytes','util':'vram_device_util_pct','hami':'hami_container_device_memory_bytes{pod=~"vram-.*"}','requested':'vram_live_requested_bytes','free':'vram_free_bytes','total':'vram_total_bytes','scrape':'up{job="vram"}'}
for name,q in queries.items():
 url='http://127.0.0.1:19096/api/v1/query_range?'+urllib.parse.urlencode({'query':q,'start':start,'end':end,'step':1})
 data=urllib.request.urlopen(url,timeout=60).read();j=json.loads(data);assert j['status']=='success'
 with lzma.open(E/(name+'.json.xz'),'wb') as f:f.write(data)
(E/'queries.json').write_text(json.dumps({'start_utc':start,'end_utc':end,'step_seconds':1,'queries':queries,'raw_observer_nominal_interval_seconds':.5,'note':'Initial Prometheus scrape rejected missing Content-Type; fixed before later complete intervals. Raw observer data retained separately. No interpolation or reconstructed samples.'},indent=2)+'\n')
with (E/'physical.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['utc','device_mib','process_sum_mib','unattributed_device_mib','util_pct']);w.writeheader()
 for r in rows:
  try:pm=sum(int(l.split(',')[1].strip()) for l in r['processes'].splitlines() if l.strip())
  except ValueError:continue
  w.writerow({'utc':r['utc'],'device_mib':r['gpu_mib'],'process_sum_mib':pm,'unattributed_device_mib':r['gpu_mib']-pm,'util_pct':r['util_pct']})
print('Monitoring exported',len(rows),'samples')
