"""Legacy Conv2d gradients and SGD correctness. No CPU fallback or benchmarking."""
import argparse
import copy
import json
import os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--mode',choices=['cpu','gpu'],default='gpu')
p.add_argument('--backend',choices=['legacy','default'],required=True)
p.add_argument('--case',choices=['minimal','matrix','input-only','weight-only','accumulate'],default='minimal')
p.add_argument('--results',type=Path,default=Path('/results'))
a=p.parse_args()
assert a.backend=='legacy', 'this bounded training probe requires the explicit legacy backend'
os.environ['TORCH_CUDNN_V8_API_DISABLED']='1'
assert os.environ.get('DISABLE_ADDMM_CUDA_LT')!='1'
import torch
torch.set_num_threads(1);torch.manual_seed(20261113)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.backends.cudnn.benchmark=False;assert torch.backends.cudnn.enabled
a.results.mkdir(parents=True,exist_ok=True)
def emit(stage,**kw):print(json.dumps(dict(stage=stage,**kw)),flush=True)
def snap(t):return t.detach().cpu().clone()
emit('environment',torch=torch.__version__,cuda=torch.version.cuda,cudnn=torch.backends.cudnn.version(),
     mode=a.mode,backend=a.backend,case=a.case,rtol=1e-4,atol=1e-6)
configs=[(True,1,1,True)] if a.case!='matrix' else [
    (b,s,p,d) for b in (False,True) for s in (1,2) for p in (0,1) for d in (True,False)]
need_input=a.case!='weight-only';need_weights=a.case!='input-only'
microbatches=2 if a.case=='accumulate' else 1
cpu_records={};gpu_records={};initial_records={};comparisons=[]
def run(model,data,target,device,stream=None):
    model=copy.deepcopy(model).to(device)
    for parameter in model.parameters():parameter.requires_grad_(need_weights)
    optimizer=torch.optim.SGD(model.parameters(),lr=.01,foreach=False,fused=False) if need_weights else None
    inp_data=data.to(device);target_data=target.to(device)
    if device=='cuda':torch.cuda.synchronize()
    records={}
    context=torch.cuda.stream(stream) if device=='cuda' else __import__('contextlib').nullcontext()
    with context:
        for step in range(1,4):
            inp=inp_data.detach().clone().requires_grad_(need_input)
            if optimizer:optimizer.zero_grad(set_to_none=True)
            before={n:snap(v) for n,v in model.named_parameters()}
            for micro in range(microbatches):
                emit('forward_start',device=device,step=step,micro=micro)
                output=model(inp)
                if device=='cuda':assert output.is_cuda;stream.synchronize()
                emit('forward_done',device=device,step=step,micro=micro)
                loss=torch.nn.functional.mse_loss(output,target_data)
                emit('backward_start',device=device,step=step,micro=micro)
                loss.backward()
                if device=='cuda':stream.synchronize()
                emit('backward_done',device=device,step=step,micro=micro)
            record={'output':snap(output),'loss':snap(loss)}
            if need_input:
                assert inp.grad is not None
                record['input_grad']=snap(inp.grad)
                assert record['input_grad'].abs().max().item()>0
            else:assert inp.grad is None
            for name,param in model.named_parameters():
                if need_weights:
                    assert param.grad is not None
                    record['grad/'+name]=snap(param.grad)
                    assert record['grad/'+name].abs().max().item()>0
                else:assert param.grad is None
            if optimizer:optimizer.step()
            if device=='cuda':stream.synchronize()
            after={n:snap(v) for n,v in model.named_parameters()}
            assert any(not torch.equal(before[n],after[n]) for n in before)==need_weights
            record.update({'weight/'+n:t for n,t in after.items()})
            assert all(torch.isfinite(t).all().item() for t in record.values())
            records[step]=record
            emit('step_done',device=device,step=step,optimizer_updated=need_weights)
    return records

for bias,stride,padding,deterministic in configs:
    torch.backends.cudnn.deterministic=deterministic
    label=f'b{int(bias)}-s{stride}-p{padding}-d{int(deterministic)}'
    emit('configuration',label=label)
    model=torch.nn.Conv2d(3,4,3,stride=stride,padding=padding,bias=bias).train()
    data=torch.randn(2,3,8,8);side=(8+2*padding-3)//stride+1
    target=torch.randn(2,4,side,side)
    initial_records[label]=dict(input=data,target=target,state={k:snap(v) for k,v in model.state_dict().items()},
                               stride=stride,padding=padding,bias=bias,need_input=need_input,
                               need_weights=need_weights,microbatches=microbatches)
    cpu_records[label]=run(model,data,target,'cpu')
    torch.save(initial_records,a.results/'initial.pt');torch.save(cpu_records,a.results/'cpu.pt')
    if a.mode=='cpu':continue
    for name in ('default','explicit'):
        stream=torch.cuda.default_stream() if name=='default' else torch.cuda.Stream()
        gpu=run(model,data,target,'cuda',stream)
        key=label+'/'+name;gpu_records[key]=gpu
        torch.save(gpu_records,a.results/'gpu.pt')
        for step,reference in cpu_records[label].items():
            assert set(reference)==set(gpu[step])
            for tensor,expected in reference.items():
                actual=gpu[step][tensor]
                ok=torch.allclose(actual,expected,rtol=1e-4,atol=1e-6)
                comparisons.append(dict(key=key,step=step,tensor=tensor,passed=ok,max_abs=(actual-expected).abs().max().item()))
        (a.results/'comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
        assert all(x['passed'] for x in comparisons),[x for x in comparisons if not x['passed']]
emit('PASS',configs=len(configs),gpu_training_steps=len(gpu_records)*3,
     gpu_backward_calls=len(gpu_records)*3*microbatches,compared_tensors=len(comparisons),
     backward_data=need_input,backward_filter=need_weights)
