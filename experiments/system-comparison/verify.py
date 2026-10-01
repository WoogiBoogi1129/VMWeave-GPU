"""Validate completeness and comparability independently of which system wins."""
from common import *
summary=json.loads((OUT/'summary.json').read_text());assert summary['complete']
cpu=json.loads((OUT/'cpu-summary.json').read_text());protocol=json.loads((OUT/'protocol.json').read_text())
hashes=protocol['artifact_hashes'];errors=[];checked=[]
for pair in protocol['pairs']:
 for system in pair['order']:
  name=f"sc-r{pair['repeat']}-{system.lower()}";p=OUT/'runs'/name
  try:
   result=json.loads((p/'execution.json').read_text());assert result['exit_code']==0 and len(result['results'])==8
   assert all(r['status']=='PASS' and r['mismatches']==0 and r['elapsed_s']>=60 for r in result['results'])
   assert not (p/'failure.json').exists();assert json.loads((p/'cleanup.json').read_text())['released']
   condition=json.loads((p/'condition.json').read_text());assert condition['shift']==pair['shift'] and condition['warmup_min_s']==10 and not condition['metrics']
   events=[json.loads(l) for l in (p/'stdout.jsonl').read_text().splitlines() if l.startswith('{')]
   warm=[x for x in events if x['event']=='WARMUP_END'];assert len(warm)==8 and all(x['elapsed']>=10 and x['completed']>=50 for x in warm)
   runtime=json.loads((p/'runtime-libraries.json').read_text());assert runtime
   identity=json.loads((p/'identity.json').read_text());assert identity['gpu_uuid']==GPU
   if system=='S':
    assert json.loads((p/'channel-released.json').read_text())['status']['phase']=='Released'
    for r in runtime:
     e=r['environment'];assert r['executable_sha256']==hashes['flyt-shm-worker'] and e['FLYT_METRICS']=='0'
     assert not e['FLYT_WAIT_MODE'] and not e['FLYT_COPY_MODE'] and not e['FLYT_SPIN_US']
     assert e['GPU_CORE_UTILIZATION_POLICY']=='FORCE' and e['CUDA_DEVICE_SM_LIMIT']=='100'
     assert any('libvgpu' in f for f in r['library_hashes']) and not e['CUDA_MPS_PIPE_DIRECTORY']
    assert 'FLYT_METRIC' not in (p/'stderr.txt').read_text()
    binaries=['libflyt_guest.so','probe-S','work.ptx']
   else:
    assert identity['sm_count']==protocol['physical_sm_count']
    transport=[x for x in events if x['event']=='TRANSPORT'];assert len(transport)==1 and transport[0]['socktype']==1 and transport[0]['connection_is_local']==0
    assert any('cricket-rpc-server' in r['command'] for r in runtime)
    assert any('nvidia-cuda-mps-server' in r['command'] for r in runtime)
    assert not any('libvgpu' in f for r in runtime for f in r['library_hashes'])
    assert (p/'tcp-connections.txt').stat().st_size>0
    binaries=['cricket-client.so','probe-T','work.cubin']
   lines=(p/'guest-artifact-hashes.txt').read_text().splitlines()
   for binary in binaries:assert any(x.split()[0]==hashes[binary] and x.split()[1].endswith('/'+binary) for x in lines),binary
   checked.append(name)
  except (AssertionError,KeyError,FileNotFoundError,ValueError) as e:errors.append({'run':name,'error':str(e) or type(e).__name__})
for system in ['T','S']:
 if len(cpu['summary'][system])!=8 or any(x['repeats']!=5 or x['min_coverage']<.95 for x in cpu['summary'][system].values()):errors.append({'cpu':system,'error':'Missing windows or <95% coverage'})
comparison={k:{'latency_reduction':1-summary['summary']['S'][k]['mean_us']/v['mean_us'],'S_over_T':summary['summary']['S'][k]['mean_us']/v['mean_us']} for k,v in summary['summary']['T'].items()}
save(OUT/'validation.json',{'complete':not errors,'sessions':checked,'errors':errors,'comparison':comparison,'scope':'Whole-system comparison. Validation does not require SHM to win and does not attribute all differences to transport.'})
print(json.dumps({'complete':not errors,'errors':errors,'comparison':comparison},indent=2))
if errors:raise SystemExit(1)
