#!/usr/bin/env python3
"""Audit saved training tensors using explicit convolution gradients and SGD.

CPU reference uses unfold/matmul/fold, not Conv2d autograd backward. GPU output
is loaded on CPU; this script neither executes GPU code nor trusts pass flags.
"""
import argparse
import json
from pathlib import Path
import torch
import torch.nn.functional as F

p=argparse.ArgumentParser()
p.add_argument('--results',type=Path,default=Path(__file__).resolve().parent/'results/20261113')
a=p.parse_args()
torch.set_num_threads(1)
records=[]
def read(root,name):return torch.load(root/name,map_location='cpu',weights_only=True)
def check(run,name,reference,actual):
    torch.testing.assert_close(actual,reference,rtol=1e-4,atol=1e-6)
    records.append(dict(run=run,tensor=name,shape=list(actual.shape),max_abs=(actual-reference).abs().max().item()))

for run,count in [('candidate-input-v2',30),('candidate-weight',36),('candidate-minimal',42),
                  ('candidate-matrix',576),('candidate-matrix-repeat',576),('candidate-accumulate',42)]:
    root=a.results/run
    initial=read(root,'initial.pt');cpu=read(root,'cpu.pt');gpu=read(root,'gpu.pt')
    references={}
    for label,c in initial.items():
        x=c['input'];target=c['target'];state={n:t.clone() for n,t in c['state'].items()}
        cols=F.unfold(x,kernel_size=3,padding=c['padding'],stride=c['stride'])
        steps={}
        for step in range(1,4):
            y=F.conv2d(x,state['weight'],state.get('bias'),stride=c['stride'],padding=c['padding'])
            dy=(2*(y-target)/y.numel()).flatten(2)
            dw=torch.einsum('nol,nil->oi',dy,cols).reshape_as(state['weight'])*c['microbatches']
            dxcols=torch.einsum('oi,nol->nil',state['weight'].flatten(1),dy)
            dx=F.fold(dxcols,x.shape[-2:],kernel_size=3,padding=c['padding'],stride=c['stride'])*c['microbatches']
            grads={'weight':dw}
            if c['bias']:grads['bias']=dy.sum((0,2))*c['microbatches']
            result={'output':y,'loss':((y-target)**2).mean()}
            if c['need_input']:result['input_grad']=dx
            if c['need_weights']:
                result.update({'grad/'+n:t for n,t in grads.items()})
                state={n:t-.01*grads[n] for n,t in state.items()}
            result.update({'weight/'+n:t.clone() for n,t in state.items()})
            assert set(result)==set(cpu[label][step])
            for n,t in result.items():
                torch.testing.assert_close(cpu[label][step][n],t,rtol=1e-4,atol=1e-6)
            steps[step]=result
        references[label]=steps
    assert set(gpu)=={label+'/'+stream for label in initial for stream in ('default','explicit')}
    start=len(records)
    for key,steps in gpu.items():
        assert set(steps)=={1,2,3}
        for step,actual in steps.items():
            expected=references[key.split('/')[0]][step]
            assert set(expected)==set(actual)
            for n,t in expected.items():check(run,f'{key}/{step}/{n}',t,actual[n])
    assert len(records)-start==count

run='regression/candidate-forward'
root=a.results/run;cpu=read(root,'cpu.pt');gpu=read(root,'gpu.pt')
assert len(gpu)==96
for key,actual in gpu.items():
    label=key.split('/')[0];reference=cpu[label]
    flags={x[0]:int(x[1:]) for x in label.split('-')};state=reference['state']
    expected=F.conv2d(reference['input'],state['weight'],state.get('bias'),stride=flags['s'],padding=flags['p'])
    check(run,key,expected,actual)
for name,count in [('candidate-mlp',22),('candidate-lstm',36),('candidate-lstm-repeat',36)]:
    run='regression/'+name;root=a.results/run;cpu=read(root,'cpu.pt');gpu=read(root,'cuda.pt')
    assert set(cpu)==set(gpu)=={1,5};start=len(records)
    for step in cpu:
        assert set(cpu[step])==set(gpu[step])
        for key in cpu[step]:check(run,f'{step}/{key}',cpu[step][key],gpu[step][key])
    assert len(records)-start==count
report=dict(status='PASS',auditTorch=torch.__version__,rtol=1e-4,atol=1e-6,
            cnnReference='explicit unfold/matmul/fold gradients and manual SGD',
            tensors=len(records),max_abs=max(x['max_abs'] for x in records),comparisons=records)
(a.results/'tensor-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='comparisons'},indent=2))
