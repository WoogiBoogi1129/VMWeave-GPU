import json,math,statistics,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent
if not (O/'comparison.json').exists():O=Path('experiments/ai-passthrough/results/20261026-rodinia-steady')
summary=json.loads((O/'comparison.json').read_text())
assert len(summary)==16
for s in summary:
 files=sorted((O/'formal').glob('*/'+s['mode']+'/'+s['workload']+'/result.json'));assert len(files)==5
 values=[]
 for f in files:
  r=json.loads(f.read_text());assert r['correct'] and r['returncode']==0
  expected=json.loads((O/'qualification/native'/s['workload']/'result.json').read_text())['hashes']['output-02.bin']
  hashes=list(r['hashes'].values()) if isinstance(r['hashes'],dict) else [line.split()[0] for line in r['hashes'].splitlines()]
  assert len(hashes)==4 and all(d==expected for d in hashes),f
  assert [a['iteration'] for a in r['samples']]==[0,1,2,3]
  if 'binary_sha256' in r:assert r['binary_sha256'].split()[0]==json.loads((O/'manifest.json').read_text())['binaries'][s['workload']]
  assert len([x for x in r['samples'] if x['warmup']])==2
  a=[x['seconds'] for x in r['samples'] if not x['warmup']];assert len(a)==2 and all(math.isfinite(v) and v>0 for v in a);values+=a
 assert s['n']==10 and math.isclose(s['mean_s'],statistics.mean(values),rel_tol=1e-12)
 for mode,key in [('native','native_overhead_pct'),('passthrough','passthrough_overhead_pct')]:
  reference=next(x for x in summary if x['mode']==mode and x['workload']==s['workload']);assert math.isclose(s[key],100*(s['mean_s']/reference['mean_s']-1),abs_tol=1e-9)
diagnostics=list((O/'diagnostic').glob('*/*/*/result.json'));assert len(diagnostics)==16
for p in diagnostics:
 r=json.loads(p.read_text());assert r['correct'] and r['returncode']==0 and len(r['samples'])==3
 d=json.loads((p.parent/'api-profile.json').read_text());assert len(d['apis'])==12 and all(x['calls']>=0 and x['wall_ns']>=0 for x in d['apis'].values())
p=O/'SHA256SUMS.json'
if p.exists():
 for name,digest in json.loads(p.read_text()).items():assert hashlib.sha256((O/name).read_bytes()).hexdigest()==digest,name
print('PASS: 160 measured samples, 160 excluded warmups, 5 independent sessions per workload/mode; statistics and checksums')
