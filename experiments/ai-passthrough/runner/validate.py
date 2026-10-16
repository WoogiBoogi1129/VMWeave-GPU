"""Audit completed experiment evidence without launching GPU workloads."""
import hashlib,json,math,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];E=R/'results/20261016'
correct=json.loads((E/'correctness.json').read_text());expected={r['condition'] for r in correct['conditions'] if r['status']=='PASS'}
assert len(expected)==8,expected
supplement='--equal-budget' in sys.argv
blocks=3 if supplement else 5
if supplement:
 E=E/'equal-budget'
 expected={'small-32-resident','medium-1024-resident'}
sha=hashlib.sha256((R/'runner/bench.py').read_bytes()).hexdigest();runs=[]
for block in range(1,blocks+1):
 for backend in ['vmweave','passthrough']:
  root=E/f'b{block}-{backend}';assert (root/'complete.json').is_file(),root
  if supplement:
   complete=json.loads((root/'complete.json').read_text())
   assert complete['host_cpu_budget']==12
   assert complete['guest_vcpus']==(8 if backend=='vmweave' else 12)
   if backend=='passthrough':
    identity=E.parent/'identities'/f'ai-perf-eq-p-{block}-1016'
    assert json.loads((identity/'vmi.json').read_text())['spec']['domain']['cpu']['cores']==12
    affinity=json.loads((identity/'affinity.json').read_text())
    assert affinity['cpu_set']=='32-43' and affinity['processes']
    assert all(t['cpus']==list(range(32,44)) for p in affinity['processes'] for t in p['threads'])
  actual={p.parent.name for p in root.glob('*/result.json')};assert actual==expected,(root,actual)
  for condition in sorted(expected):
   p=root/condition;r=json.loads((p/'result.json').read_text());assert json.loads((p/'exit.json').read_text())['returncode']==0
   assert r['source_sha256']==sha and r['mode']=='performance'
   assert r['affinity']==list(range(12 if supplement and backend=='passthrough' else 8))
   assert r['warmup_seconds']>=30 and r['elapsed_seconds']>=120
   assert r['steps']>0 and math.isfinite(r['final_loss'])
   assert math.isclose(r['samples_per_second'],r['steps']*r['batch']/r['elapsed_seconds'],rel_tol=1e-12)
   raw=[json.loads(l) for l in (p/'host-cpu.jsonl').read_text().splitlines()];assert sum('processes' in x for x in raw)>100
   assert len((p/'gpu.csv').read_text().splitlines())>30
   if backend=='vmweave':
    ids=[x for x in raw if x.get('event')=='worker_identity' and '--session' in x.get('command','')]
    assert ids and any(x['environment'].get('CUDA_DEVICE_SM_LIMIT')=='100' and '/usr/local/vgpu/libvgpu.so' in x['libraries'] for x in ids)
   runs.append({'block':block,'backend':backend,'condition':condition,'fixture_sha256':r['fixture_sha256']})
for cond in expected:assert len({x['fixture_sha256'] for x in runs if x['condition']==cond})==1
result={'status':'PASS','formal_measurements':len(runs),'conditions':len(expected),'paired_blocks':blocks,'benchmark_sha256':sha,'checks':['complete blocks','matching condition matrix','zero exit status','minimum durations','finite final losses','throughput arithmetic','host/GPU samples','actual Core 100 worker library mapping','identical fixtures and workload source']}
(E/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
