"""Validate archived evidence without GPU, Kubernetes, or third-party packages."""
import csv, hashlib, json, math, statistics
from pathlib import Path
D=Path(__file__).resolve().parent

def read(path):return json.loads((D/path).read_text())
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-9),(a,b)

checksums=read('SHA256SUMS.json')
for name,digest in checksums.items():assert hashlib.sha256((D/name).read_bytes()).hexdigest()==digest,name
reference={r['workload']:r['native_host_sha256'] for r in read('native-reference.json')}
rows=list(csv.DictReader((D/'raw.csv').open()));assert len(rows)==18
keys={(r['round'],r['mode'],r['workload']) for r in rows};assert len(keys)==18
assert keys=={(r,m,w) for r in ['r1','r2','r3'] for m in ['passthrough','flyt','vmweave'] for w in reference}
for r in rows:
 source=next(x for x in read(r['log']) if x['workload']==r['workload'])
 assert source['returncode']==0 and source['sha256']==r['sha256']==reference[r['workload']]
 assert source.get('correct',source.get('matches_native_reference',False)) and r['correct']=='True'
 for f in ['seconds','startup_seconds','gpu_phase_seconds']:close(r[f],source['timing'][f])
 close(float(r['seconds']),float(r['startup_seconds'])+float(r['gpu_phase_seconds']))
 assert float(r['seconds'])>0
for s in read('comparison.json'):
 x=[float(r['seconds']) for r in rows if r['mode']==s['mode'] and r['workload']==s['workload']]
 baseline=statistics.median(float(r['seconds']) for r in rows if r['mode']=='passthrough' and r['workload']==s['workload'])
 assert len(x)==s['n']==3
 for k,v in [('median_seconds',statistics.median(x)),('min_seconds',min(x)),('max_seconds',max(x)),('sample_cv',statistics.stdev(x)/statistics.mean(x)),('throughput_relative_to_passthrough_percent',100*baseline/statistics.median(x))]:close(s[k],v)
for stage,count in [('warmup',18),('diagnostic',8)]:
 samples=[r for p in (D/stage).glob('*/*/result.json') for r in json.loads(p.read_text())];assert len(samples)==count
 assert all(r['returncode']==0 and r['sha256']==reference[r['workload']] and r.get('correct',r.get('matches_native_reference',False)) for r in samples)
assert read('cleanup.json')['production_channel']=='Ready'
assert read('manifest.json')['formal_runs']==18 and read('manifest.json')['status']=='COMPLETE'
print(f'PASS: {len(checksums)} checksums; 18 formal samples; statistics; 18 excluded warmups; 8 separate diagnostics; recorded cleanup')
