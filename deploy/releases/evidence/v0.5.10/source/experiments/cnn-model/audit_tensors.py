#!/usr/bin/env python3
"""Replay saved CNN training with manual backward equations and SGD on CPU."""
import argparse
import json
from pathlib import Path
import torch
import torch.nn.functional as F
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=Path(__file__).resolve().parent/'results/20261113')
p.add_argument('--run-prefix',default='candidate-',help='Prefix for the five archived run names')
a=p.parse_args();torch.set_num_threads(1);records=[]
def load(root,name):return torch.load(root/name,map_location='cpu',weights_only=True)
def replay(c):
    state={n:t.clone() for n,t in c['state'].items()};steps={}
    for step in range(1,6):
        x=c['input'][step-1];target=c['target'][step-1];cache=[];out=x
        for i,kind in enumerate(c['architecture']):
            inp=out;indices=None;prefix=str(i)+'.'
            if kind=='Conv2d':out=F.conv2d(inp,state[prefix+'weight'],state[prefix+'bias'],padding=1)
            elif kind=='ReLU':out=inp.clamp_min(0)
            elif kind=='MaxPool2d':out,indices=F.max_pool2d(inp,2,return_indices=True)
            elif kind=='Flatten':out=inp.flatten(1)
            elif kind=='Linear':out=F.linear(inp,state[prefix+'weight'],state[prefix+'bias'])
            else:raise AssertionError(kind)
            cache.append((inp,indices))
        if c['case'] in ('cnn','mnist'):
            loss=-F.log_softmax(out,dim=1).gather(1,target[:,None]).mean()
            dy=out.softmax(1);dy[torch.arange(len(target)),target]-=1;dy/=len(target)
        else:loss=((out-target)**2).mean();dy=2*(out-target)/out.numel()
        grads={}
        for i in reversed(range(len(cache))):
            inp,indices=cache[i];kind=c['architecture'][i];prefix=str(i)+'.'
            if kind=='Linear':
                grads[prefix+'weight']=dy.T@inp;grads[prefix+'bias']=dy.sum(0)
                dy=dy@state[prefix+'weight']
            elif kind=='Flatten':dy=dy.reshape_as(inp)
            elif kind=='MaxPool2d':
                dx=torch.zeros_like(inp).flatten(2)
                dx.scatter_add_(2,indices.flatten(2),dy.flatten(2));dy=dx.reshape_as(inp)
            elif kind=='ReLU':dy=dy*(inp>0)
            elif kind=='Conv2d':
                w=state[prefix+'weight'];cols=F.unfold(inp,3,padding=1);flat=dy.flatten(2)
                grads[prefix+'weight']=torch.einsum('nol,nil->oi',flat,cols).reshape_as(w)
                grads[prefix+'bias']=dy.sum((0,2,3))
                dy=F.fold(torch.einsum('oi,nol->nil',w.flatten(1),flat),inp.shape[-2:],3,padding=1)
        result={'output':out,'loss':loss,'input_grad':dy}
        assert set(grads)==set(state)
        result.update({'grad/'+n:t for n,t in grads.items()})
        state={n:t-c['lr']*grads[n] for n,t in state.items()}
        result.update({'weight/'+n:t.clone() for n,t in state.items()});steps[step]=result
    return steps

for run,count in [('candidate-relu',70),('candidate-pool',70),('candidate-cnn',300),
                  ('candidate-cnn-repeat',300),('candidate-mnist',300)]:
    run=a.run_prefix+run.removeprefix('candidate-')
    root=a.results/run;c=load(root,'initial.pt');cpu=load(root,'cpu.pt');gpu=load(root,'gpu.pt')
    expected=replay(c)
    keys={'d1','d0'} if c['case'] in ('cnn','mnist') else {'d1'}
    assert set(cpu)==keys and set(gpu)=={k+'/'+s for k in keys for s in ('default','explicit')}
    start=len(records)
    for kind,collection in [('cpu',cpu),('gpu',gpu)]:
        for label,steps in collection.items():
            assert set(steps)==set(expected)
            for step,actual in steps.items():
                assert set(actual)==set(expected[step])
                for tensor,t in expected[step].items():
                    torch.testing.assert_close(actual[tensor],t,rtol=1e-4,atol=1e-6,msg=lambda m:f'{run}/{kind}/{label}/{step}/{tensor}: {m}')
                    if kind=='gpu':records.append(dict(run=run,key=label,step=step,tensor=tensor,
                        max_abs=(actual[tensor]-t).abs().max().item()))
    assert len(records)-start==count
report=dict(status='PASS',auditTorch=torch.__version__,tensors=len(records),rtol=1e-4,atol=1e-6,
            method='manual Conv/ReLU/MaxPool/Linear/loss backward and SGD; no autograd backward',
            max_abs=max(x['max_abs'] for x in records),comparisons=records)
(a.results/'tensor-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='comparisons'},indent=2))
