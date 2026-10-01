"""Fail closed on incomplete repetitions, wrong binaries, policies or outputs."""
import hashlib
from common import *
summary=json.loads((OUT/'summary.json').read_text());assert summary['complete']
protocol=json.loads((OUT/'protocol.json').read_text());hashes=json.loads((OUT/'build/artifact-hashes.json').read_text())
errors=[];checked=[]
for rep in range(1,6):
 for variant in ['base','wait','copy','both']:
  name=f'sf-r{rep}-{variant}';p=OUT/'runs'/name
  try:
   execution=json.loads((p/'execution.json').read_text());assert execution['exit_code']==0
   assert len(execution['results'])==5 and all(r['status']=='PASS' and r['mismatches']==0 for r in execution['results'])
   assert json.loads((p/'channel-released.json').read_text())['status']['phase']=='Released'
   assert json.loads((p/'cleanup.json').read_text())['released']
   actual=json.loads((p/'runtime-libraries.json').read_text());assert actual
   for r in actual:
    e=r['environment'];assert r['executable_sha256']==hashes['flyt-shm-worker']
    assert e['FLYT_WAIT_MODE']==protocol['variants'][variant]['wait'] and e['FLYT_COPY_MODE']==protocol['variants'][variant]['copy']
    if variant in ['wait','both']:assert e['FLYT_SPIN_US']=='0'
    assert e['GPU_CORE_UTILIZATION_POLICY']=='FORCE' and e['CUDA_DEVICE_SM_LIMIT']=='100'
    assert any('libvgpu' in x for x in r['library_hashes']) and not e['CUDA_MPS_PIPE_DIRECTORY']
   for binary in ['libflyt_guest.so','probe-S']:
    assert any(line.split()[0]==hashes[binary] and line.split()[1].endswith('/'+binary) for line in (p/'guest-artifact-hashes.txt').read_text().splitlines())
   metrics=[json.loads(x) for x in (p/'stderr.txt').read_text().splitlines() if x.startswith('{"event":"FLYT_')]
   waits=[x for x in metrics if x['event']=='FLYT_WAIT'];assert any(x['role']=='guest-io' for x in waits)
   worker_metrics=[json.loads(x) for x in (p/'worker-output.txt').read_text().splitlines() if x.startswith('{"event":"FLYT_')]
   waits += [x for x in worker_metrics if x['event']=='FLYT_WAIT']
   assert any(x['role']=='worker' for x in waits)
   if variant in ['wait','both']:assert all(x['spin_calls']==0 for x in waits)
   checked.append(name)
  except (AssertionError,KeyError,FileNotFoundError,ValueError) as e:errors.append({'run':name,'error':repr(e)})
cpu=json.loads((OUT/'cpu-summary.json').read_text())
for v in ['base','wait','copy','both']:
 if len(cpu['summary'][v])!=5 or any(x['repeats']!=5 or x['min_coverage']<.7 for x in cpu['summary'][v].values()):errors.append({'cpu':v,'error':'insufficient window coverage'})
baseline=summary['summary']['base'];both=summary['summary']['both']
improvements={k:1-both[k]['mean_us']/baseline[k]['mean_us'] for k in baseline}
targets=all(improvements[k]>=.5 for k in ['query','kernel']) and all(improvements[k]>=.25 for k in ['h2d-16777216','d2h-16777216'])
p95=all(both[k]['mean_p95_us']<=baseline[k]['mean_p95_us']*1.1 for k in baseline)
cpu_cost=all(cpu['summary']['both'][k]['cpu_us_iteration']<=v['cpu_us_iteration']*1.1 for k,v in cpu['summary']['base'].items())
save(OUT/'validation.json',{'complete':not errors,'checked_sessions':checked,'errors':errors,'improvements':improvements,
 'latency_targets_pass':targets,'p95_regression_guard_pass':p95,'cpu_per_iteration_guard_pass':cpu_cost,'candidate_eligible':not errors and targets and p95 and cpu_cost,
 'scope':'Eligibility requires review of saturated CPU and per-iteration CPU costs. No quota enforcement or TCP-only claim.'})
print(json.dumps({'errors':errors,'latency_targets_pass':targets,'p95_regression_guard_pass':p95,'improvements':improvements},indent=2))
if errors:raise SystemExit(1)
