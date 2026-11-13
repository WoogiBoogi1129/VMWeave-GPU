#!/usr/bin/env python3
"""Recompute CPU references and compare saved GPU tensors independently of flags."""
import argparse
import json
from pathlib import Path
import torch

p = argparse.ArgumentParser()
p.add_argument('--results', type=Path, default=Path(__file__).resolve().parent/'results/20261113-vm')
a = p.parse_args()
torch.set_num_threads(1)
records = []
def check(run, name, reference, actual):
    assert reference.device.type=='cpu' and actual.device.type=='cpu'
    torch.testing.assert_close(actual, reference, rtol=1e-4, atol=1e-6)
    records.append(dict(run=run,tensor=str(name),shape=list(actual.shape),
                        max_abs=(actual-reference).abs().max().item()))
for run in ('candidate-minimal','candidate-matrix','candidate-matrix-repeat'):
    root = a.results/run
    cpu = torch.load(root/'cpu.pt', map_location='cpu', weights_only=True)
    gpu = torch.load(root/'gpu.pt', map_location='cpu', weights_only=True)
    for key, actual in gpu.items():
        label = key.split('/')[0]; reference = cpu[label]
        flags = {x[0]:int(x[1:]) for x in label.split('-')}
        state = reference['state']
        recalculated = torch.nn.functional.conv2d(reference['input'],state['weight'],state.get('bias'),
                                                  stride=flags['s'],padding=flags['p'])
        torch.testing.assert_close(recalculated,reference['output'],rtol=1e-4,atol=1e-6)
        check(run,key,recalculated,actual)
    assert len(gpu)==(6 if run=='candidate-minimal' else 96)
for run in ('candidate-mlp','candidate-lstm','candidate-lstm-repeat'):
    root = a.results/'regression'/run
    cpu = torch.load(root/'cpu.pt',map_location='cpu',weights_only=True)
    gpu = torch.load(root/'cuda.pt',map_location='cpu',weights_only=True)
    assert set(cpu)==set(gpu)=={1,5}
    for step in cpu:
        assert set(cpu[step])==set(gpu[step])
        for key in cpu[step]:
            check(run,f'{step}/{key}',cpu[step][key],gpu[step][key])
report = dict(status='PASS',auditTorch=torch.__version__,rtol=1e-4,atol=1e-6,
              tensors=len(records),max_abs=max(x['max_abs'] for x in records),comparisons=records)
(a.results/'tensor-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='comparisons'},indent=2))
