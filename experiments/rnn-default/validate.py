#!/usr/bin/env python3
"""Offline audit of the recorded experiment; does not execute GPU work."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path(__file__).parent/'results/20261108');a=p.parse_args();r=a.results
required=['candidate-v3b-lstm','candidate-v3b-lstm-repeat','candidate-v3b-continuous','candidate-v3b-resume','candidate-v3b-mlp','candidate-v3b-basic-after']
for name in required:
 d=r/name;status=json.loads((d/'exit.json').read_text());assert status['returncode']==0 and not status['timeout'],name
 pod=json.loads((d/'pod.json').read_text());assert pod['status']['phase']=='Succeeded',name
 manifest=json.loads((d/'submitted.json').read_text());env={e['name']:e.get('value') for e in manifest['spec']['containers'][0].get('env',[])}
 assert 'DISABLE_ADDMM_CUDA_LT' not in env and 'TORCH_CUDNN_V8_API_DISABLED' not in env,name
 assert any(json.loads(line).get('stage')=='PASS' for line in (d/'stdout.txt').read_text().splitlines() if line.startswith('{')),name
 if 'basic' not in name:
  comparisons=json.loads((d/'comparison.json').read_text());assert comparisons and all(x['pass_'] for x in comparisons),name
for name,steps in [('candidate-v3b-continuous',128),('candidate-v3b-resume',96)]:
 m=json.loads((r/name/'cuda-metrics.json').read_text());assert m['steps']==steps and len(m['losses'])==steps
trace=(r/'final-worker.log').read_text()
for api in [0x3314,0x3315,0x3316,0x3322]:assert f'library api={api} result=0' in trace,hex(api)
proof=json.loads((r/'continuous-gpu-observation.json').read_text());assert proof['sessions'] and proof['gpu']
assert any(int(v.split('NSpid:')[1].split()[-1]) in {s['pid'] for s in proof['sessions']} for v in proof['hostProcessStatus'].values())
cleanup=json.loads((r/'cleanup.json').read_text());assert cleanup['originalVMRestored'] and cleanup['sessionsReclaimed'] and cleanup['candidateResourcesRemoved']
audit=json.loads((r/'offline-tensor-audit.json').read_text())
assert audit['passed'] and len(audit['checks'])==108 and all(row['finite'] and row['pass_'] for row in audit['checks'])
for line in (r/'SHA256SUMS').read_text().splitlines():
 sha,name=line.split('  ',1);assert hashlib.sha256((r/name).read_bytes()).hexdigest()==sha,name
print('PASS: recorded default-path learning, recurrence, restart, GPU identity, cleanup and evidence hashes')
