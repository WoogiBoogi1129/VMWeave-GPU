"""Staged Conv/ReLU/MaxPool/Linear training; fixed CPU/GPU correctness bounds."""
import argparse
import base64
import contextlib
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--mode',choices=['cpu','gpu'],default='gpu')
p.add_argument('--backend',choices=['legacy','default'],required=True)
p.add_argument('--case',choices=['relu','pool','cnn','mnist'],required=True)
p.add_argument('--results',type=Path,default=Path('/results'))
a=p.parse_args();assert a.backend=='legacy'
os.environ['TORCH_CUDNN_V8_API_DISABLED']='1'
assert os.environ.get('DISABLE_ADDMM_CUDA_LT')!='1'
import torch
from torch import nn
torch.set_num_threads(1);torch.manual_seed(20261113)
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.backends.cudnn.benchmark=False;assert torch.backends.cudnn.enabled
a.results.mkdir(parents=True,exist_ok=True)
def emit(stage,**kw):print(json.dumps(dict(stage=stage,**kw)),flush=True)
def snap(t):return t.detach().cpu().clone()
full=a.case in ('cnn','mnist');mnist=a.case=='mnist'
channels=1 if mnist else 3;side=28 if mnist else 32;batch=16 if mnist else 8
layers=[nn.Conv2d(channels,8,3,padding=1),nn.ReLU()]
if a.case!='relu':layers.append(nn.MaxPool2d(2))
if full:layers += [nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Flatten(),nn.Linear(16*(side//4)**2,10)]
base=nn.Sequential(*layers).train()
fixture_hash=None
if mnist:
    fixture=Path(os.environ.get('MNIST_FIXTURE','/work/mnist.b64')).read_bytes()
    fixture_hash=hashlib.sha256(fixture).hexdigest()
    blob=gzip.decompress(base64.b64decode(fixture));assert len(blob)==1280*785
    images=torch.frombuffer(bytearray(blob[:1024*784]),dtype=torch.uint8).reshape(1024,1,28,28).float()/255
    labels=torch.frombuffer(bytearray(blob[1024*784:1024*785]),dtype=torch.uint8).long()
    data=images[:80].reshape(5,batch,channels,side,side).clone();targets=labels[:80].reshape(5,batch).clone()
else:
    data=torch.randn(5,batch,channels,side,side)
    if full:targets=torch.randint(0,10,(5,batch))
    else:
        outside=side if a.case=='relu' else side//2
        targets=torch.randn(5,batch,8,outside,outside)
initial=dict(case=a.case,state={n:snap(t) for n,t in base.state_dict().items()},input=data,target=targets,
             channels=channels,side=side,batch=batch,steps=5,lr=.01,fixtureSHA256=fixture_hash,
             dataset='MNIST first 80 training examples' if mnist else 'synthetic',
             architecture=[type(layer).__name__ for layer in base])
torch.save(initial,a.results/'initial.pt')
emit('environment',torch=torch.__version__,cuda=torch.version.cuda,cudnn=torch.backends.cudnn.version(),
     case=a.case,backend=a.backend,mode=a.mode,parameters=sum(p.numel() for p in base.parameters()),
     architecture=initial['architecture'],dataset=initial['dataset'],rtol=1e-4,atol=1e-6)
def run(device,deterministic,stream_name):
    torch.backends.cudnn.deterministic=deterministic
    model=copy.deepcopy(base).to(device);opt=torch.optim.SGD(model.parameters(),lr=.01,foreach=False,fused=False)
    stream=(torch.cuda.default_stream() if stream_name=='default' else torch.cuda.Stream()) if device=='cuda' else None
    if device=='cuda':torch.cuda.synchronize()
    def sync():
        if device=='cuda':stream.synchronize()
    handles=[]
    for index,layer in enumerate(model):
        def hook(module,args,out,index=index):
            assert out.device.type==device;sync()
            emit('layer_forward_done',device=device,layer=index,kind=type(module).__name__,shape=list(out.shape))
        handles.append(layer.register_forward_hook(hook))
    records={}
    with torch.cuda.stream(stream) if device=='cuda' else contextlib.nullcontext():
        for step in range(1,6):
            inp=data[step-1].clone().to(device).requires_grad_();target=targets[step-1].to(device)
            opt.zero_grad(set_to_none=True);emit('forward_start',device=device,step=step)
            output=model(inp);sync()
            loss=nn.functional.cross_entropy(output,target) if full else nn.functional.mse_loss(output,target)
            sync();emit('loss_done',device=device,step=step)
            loss.backward();sync();emit('backward_done',device=device,step=step)
            assert inp.grad is not None
            record={'output':snap(output),'loss':snap(loss),'input_grad':snap(inp.grad)}
            before={n:snap(t) for n,t in model.named_parameters()}
            for name,t in model.named_parameters():
                assert t.grad is not None
                record['grad/'+name]=snap(t.grad)
                assert record['grad/'+name].abs().max().item()>0,name
            assert record['input_grad'].abs().max().item()>0
            opt.step();sync()
            for name,t in model.named_parameters():
                updated=snap(t);assert not torch.equal(before[name],updated),name
                record['weight/'+name]=updated
            assert all(torch.isfinite(t).all().item() for t in record.values())
            records[step]=record;emit('step_done',device=device,step=step,loss=record['loss'].item())
    for h in handles:h.remove()
    return records
cpu={};gpu={};comparisons=[]
for deterministic in ((True,False) if full else (True,)):
    key='d'+str(int(deterministic));emit('configuration',key=key)
    cpu[key]=run('cpu',deterministic,'default');torch.save(cpu,a.results/'cpu.pt')
    if a.mode=='cpu':continue
    for name in ('default','explicit'):
        label=key+'/'+name;gpu[label]=run('cuda',deterministic,name);torch.save(gpu,a.results/'gpu.pt')
        for step,reference in cpu[key].items():
            assert set(reference)==set(gpu[label][step])
            for tensor,expected in reference.items():
                actual=gpu[label][step][tensor]
                comparisons.append(dict(key=label,step=step,tensor=tensor,
                    passed=torch.allclose(actual,expected,rtol=1e-4,atol=1e-6),max_abs=(actual-expected).abs().max().item()))
        (a.results/'comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
        assert all(x['passed'] for x in comparisons),[x for x in comparisons if not x['passed']]
emit('PASS',gpu_training_steps=len(gpu)*5,compared_tensors=len(comparisons))
